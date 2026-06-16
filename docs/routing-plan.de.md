# Plan: Granulares Egress- & Ingress-Routing

Status: **Planungsdokument, nicht implementiert.** Beschreibt die Erweiterung
des heutigen, bewusst simplen Routing (1 Exit-VPN, 1 Domain-Liste, 1 DNAT pro
Port) zu einem granularen Policy-Routing-System für ein- und ausgehenden
Verkehr am VPS-Endpunkt. Dient als Grundlage für eine spätere
Implementierungs-Phase (siehe `Phasenplan` unten); keine Codeänderung in
diesem Schritt.

Erweitert um drei zusätzliche, eng verwandte Themen, die in der Praxis nicht
von der reinen Regel-Engine zu trennen sind:

- **Abschnitt 7**: welche Anpassungen tatsächlich serverseitig nötig sind —
  getrennt nach VPS-Betriebssystem, Router-Firmware (anderes Repo) und
  upstream `omr-admin` (anderes Projekt) — statt allem implizit dem
  Dashboard-Backend zuzuschreiben.
- **Abschnitt 8**: ein ehrlicher Audit, welche der heute nur im Wizard
  gesetzten Werte (VPS-IP, Router-Zugangsdaten, LAN-Konfiguration, Secrets)
  danach tatsächlich im Dashboard wieder änderbar sind — und ein konkreter
  Plan, das für alles technisch Mögliche nachzurüsten.
- **Abschnitt 9**: die in der Praxis sehr häufige Topologie „eigene Firewall
  hinter dem OMR-Router" (statt OMR als alleinigem Heimnetz-Router) —
  inklusive einer direkten Antwort auf die Frage, ob/wie die öffentliche
  VPS-IP an diese Firewall durchgereicht werden kann.

## 1. Ausgangslage (heutiger Stand)

| Bereich | Heute | Datei |
|---|---|---|
| Egress (VPN) | **ein** optionaler WireGuard-Exit-Peer, global `allowed_ips`, Kill-Switch an/aus | `services/wireguard_service.py`, `schemas.ExitVpn` |
| Egress (Domain) | Domain-String → `vpn` \| `wanX` \| `block`, keine Quote/Zeitfenster/Subnetz-Bedingung | `routers/qos.py`, `schemas.DomainRule` |
| Ingress | **ein** Ziel pro Port: `src_port → dest_ip:dest_port`, Proto tcp/udp/beides, an/aus | `services/shorewall_service.py`, `schemas.PortForward` |
| Firewall | einfache Allow/Block-Liste mit Zone + Port | `services/shorewall_service.py` (Presets), `routers/firewall.py` |
| QoS | 5 feste Profile, keine Kombination mit Routing-Zielen | `routers/qos.py` |

Das deckt den Demo-/Standardfall gut ab, ist aber für anspruchsvolle Setups
(mehrere Exit-VPNs für unterschiedliche Zwecke, Lastverteilung auf mehrere
Ziel-Hosts, zeit- oder quellbasierte Regeln, IPv6) nicht granular genug. Ziel
dieses Plans: ein **Policy-Routing-Layer**, der die heutigen einfachen
Endpunkte als Spezialfall ("Basic Mode") einer allgemeineren Regel-Engine
behält — bestehende UI/Wizard-Flows bleiben unverändert funktionsfähig.

## 2. Leitprinzipien (gelten für die gesamte Erweiterung)

1. **Additiv, nicht ersetzend.** `PortForward`/`ExitVpn`/`DomainRule` bleiben
   als vereinfachte Sicht erhalten; sie werden intern auf das neue Modell
   abgebildet (1 `IngressRule` bzw. 1 `EgressRule` mit genau einer Bedingung).
2. **Strikte Validierung vor jedem Schreiben**, wie bisher in
   `schemas.PortForward._validate_dest_ip` — jede neue Bedingungs-/Aktions-
   Kombination braucht einen Pydantic-Validator, bevor sie in Shorewall-,
   `ip rule`- oder `wg-quick`-Konfiguration übersetzt wird. Kein Freitext landet
   ungeprüft in einer Shell-/Konfigurationszeile.
3. **Trockenlauf vor Anwenden.** Jede Regeländerung wird zuerst gegen
   `shorewall check` (bzw. ein äquivalentes Syntax-Preflight für `ip rule`)
   geprüft; nur bei Erfolg wird `shorewall restart` / `ip route replace`
   ausgeführt. Schlägt die Prüfung fehl, bleibt die zuvor aktive Konfiguration
   unangetastet (kein Teil-Apply).
4. **Owner-Badges konsistent fortführen.** Jede neue Regel bekommt wie der
   Rest des Dashboards eine `ConfigOwner`-Zuordnung (🖥️ Router / ☁️ VPS /
   🔄 Auto-Sync), sichtbar in der Config-Karte.
5. **Demo-Modus-Parität.** Jede neue Service-Methode unterstützt weiterhin
   einen In-Memory-Demo-Pfad (`settings.demo`), damit Frontend-Entwicklung und
   `/verify`-Läufe ohne echten VPS möglich bleiben.
6. **Keine Erfindung am OMR-Kern vorbei.** Wo OpenMPTCProuter bereits einen
   Mechanismus hat (z. B. `omr-dscp`/dnsmasq-ipset für domainbasiertes
   Routing, MPTCP-Scheduler für Link-Auswahl), wird dieser angesteuert statt
   parallel neu gebaut — das Dashboard bleibt eine Bedienoberfläche für
   bestehende OMR-Mechanismen, kein Ersatz dafür.
7. **Alles, was der Wizard einmalig setzt, muss danach im Dashboard wieder
   änderbar sein** — keine Werte, die nur über manuelles `.env`-Editieren plus
   Container-Neustart korrigierbar sind. Wo eine Änderung technisch zwingend
   einen Neustart erfordert (z. B. `BIND_ADDR`, da es die Docker-Netzwerk-
   Bindung betrifft), zeigt die UI das ehrlich an, statt den Eindruck einer
   Live-Übernahme zu erwecken. Details und eine konkrete Lücken-Bestandsaufnahme
   in Abschnitt 10.

## 3. Neues Datenmodell

### 3.1 Egress: `EgressProfile` + `EgressRule`

Heute kennt das System genau **einen** Exit-Pfad. Künftig: beliebig viele
benannte Exit-Profile, auf die Regeln verweisen.

```python
class EgressProfile(BaseModel):
    id: str
    name: str                          # "Privacy-VPN", "Business-Exit", "Direkt"
    type: Literal["wireguard", "openvpn", "direct"]
    endpoint: Optional[str] = None
    public_key: Optional[str] = None
    private_key: Optional[str] = None  # nie an Client zurückgeben
    kill_switch: bool = False
    table_id: int                      # eigene `ip route` Tabelle (z. B. 100+n)
    fwmark: int                        # eigener fwmark zur Paketkennzeichnung
    enabled: bool = True

class EgressMatch(BaseModel):
    src_cidr: Optional[str] = None       # z. B. 192.168.100.0/24 oder einzelner Host
    src_link: Optional[str] = None       # nur Traffic, der ursprünglich über WAN X kam
    dest_cidr: Optional[str] = None
    dest_domain: Optional[str] = None    # FQDN/Suffix, via omr-dscp/dnsmasq-ipset
    dest_port: Optional[str] = None      # "443" oder "1000-2000"
    proto: Literal["tcp", "udp", "any"] = "any"
    time_window: Optional[str] = None    # z. B. "Mo-Fr 08:00-18:00" (Cron-ähnlich)

class EgressRule(BaseModel):
    id: str
    description: str
    priority: int                        # niedrigere Zahl = höhere Präzedenz
    match: EgressMatch
    action: Literal["profile", "wan", "block"]
    target_profile_id: Optional[str] = None   # wenn action == profile
    target_wan_id: Optional[str] = None       # wenn action == wan
    enabled: bool = True
    owner: ConfigOwner = ConfigOwner.sync
```

**Mehrere gleichzeitige Exit-Pfade:** jedes `EgressProfile` bekommt ein
eigenes `wg-quick`-Interface (`omr-exit-<id>`), eine eigene `ip route`-Tabelle
und einen eigenen `fwmark`. `EgressRule`s erzeugen `iptables -t mangle`-Regeln,
die Pakete nach Match-Kriterium markieren; `ip rule add fwmark <n> table <n>`
lenkt sie in die passende Tabelle. Damit kann z. B. "Streaming-Domains direkt,
Rest über Privacy-VPN, Firmen-Subnetz über Business-Exit" gleichzeitig aktiv
sein.

**Default/Fallback:** genau eine Regel mit `match = {}` (kein Kriterium) und
niedrigster Priorität deckt "alles andere" ab — entspricht dem heutigen
einzelnen `ExitVpn`.

### 3.2 Ingress: `IngressRule` (Ablöse-Obermenge von `PortForward`)

```python
class IngressTarget(BaseModel):
    dest_ip: str
    dest_port: int
    weight: int = 1                       # für Lastverteilung über mehrere Targets

class IngressRule(BaseModel):
    id: str
    description: str
    listen_ip: Optional[str] = None       # None = alle öffentlichen IPs des VPS
    src_port: str                          # "8080" oder "20000-20010" (Range)
    proto: Literal["tcp", "udp", "tcp/udp"] = "tcp"
    targets: list[IngressTarget]           # 1 Eintrag = heutiges Verhalten
    balance: Literal["single", "roundrobin", "weighted"] = "single"
    allow_src_cidrs: list[str] = Field(default_factory=list)  # leer = von überall
    deny_src_cidrs: list[str] = Field(default_factory=list)
    rate_limit_per_min: Optional[int] = None   # SYN/Conn-Limit via Shorewall tcrules
    time_window: Optional[str] = None
    enabled: bool = True
```

**Lastverteilung über mehrere Ziele:** Shorewall/iptables `statistic`-Match
(`nth` oder `random`) pro `weight`, gerendert als mehrere DNAT-Zeilen mit
Wahrscheinlichkeits-Gewichtung — kein externer Load-Balancer nötig.

**Quell-Filter pro Regel:** zusätzliche `loc`/`net`-Subzonen oder direkte
`SOURCE`-Spalte in der Shorewall-Regel, statt eines globalen Allow/Block.

**Portbereiche:** Shorewall unterstützt `start:end`-Portnotation nativ —
1:1-Übersetzung von `"20000-20010"`.

**1:1-Host-Exposure (volle NAT-Weiterleitung eines Hosts):** Spezialfall mit
`src_port = "0-65535"`, eigener Sicherheitswarnung im UI ("Dieser Host ist
vollständig aus dem Internet erreichbar") und Pflicht-Bestätigung vor Anwenden.

### 3.3 Gemeinsame Bausteine

- **`RoutingPreview`**: Vor dem Anwenden einer Regel berechnet der Backend
  einen Vorschau-Text ("Traffic von 192.168.100.0/24 zu *.netflix.com geht ab
  sofort direkt über WAN, nicht mehr über Privacy-VPN") — Transparenz statt
  Raten, was eine Regelkombination tatsächlich bewirkt.
- **`RoutingConflict`**: Beim Speichern prüft der Service auf Überlappungen
  (zwei Ingress-Regeln auf demselben Port/Protokoll, zwei Egress-Regeln mit
  identischem Match aber unterschiedlichem Ziel) und liefert eine 409-Antwort
  mit Klartext-Erklärung statt eines stillen Überschreibens.
- **`RoutingSimulator`**-Endpoint: `POST /routing/simulate {src, dest, port,
  proto}` → "Welcher Pfad würde für dieses Paket gewählt? Welche Regel hat
  gegriffen?" — wertvoll zum Debuggen komplexer Regelketten, ohne echten
  Traffic erzeugen zu müssen.

## 4. UI/UX-Konzept

Neue Sektion `/routing` (verlinkt von `/vps` und `/qos`, die ihre heutigen
einfachen Formulare als "Basis-Modus" behalten):

```
┌ Egress ────────────────────────────────────────────────────┐
│ Profile:  [Direkt] [Privacy-VPN ●] [Business-Exit ●] [+]    │
│                                                              │
│ Regeln (Priorität ↓):                                       │
│  1. *.netflix.com           → Direkt           [aktiv] [✎]  │
│  2. 192.168.100.0/24:firma  → Business-Exit    [aktiv] [✎]  │
│  3. (Standard, alles)       → Privacy-VPN       [aktiv] [✎]  │
│                              [+ Neue Regel]  [🔍 Simulieren] │
└──────────────────────────────────────────────────────────────┘

┌ Ingress ───────────────────────────────────────────────────┐
│ Port      Proto   Ziel(e)                      Quelle       │
│ 8080      tcp     NAS:80 (100%)                 überall      │
│ 9000-9010 tcp     App1:9000, App2:9000 (50/50)  überall      │
│ 1194      udp     Firewall:1194                 10.0.0.0/8   │
│                              [+ Neue Weiterleitung]           │
└──────────────────────────────────────────────────────────────┘
```

Regel-Editor als geführter Dialog (Bedingung → Aktion), keine Rohformulare
mit allen Feldern gleichzeitig — analog zum bestehenden
`PortForwardDialog`/Topology-Picker-Muster. Drag-Reorder für Priorität
(gleiches Interaktionsmuster wie die bereits existierende
Link-Prioritäts-Drag-and-Drop-Liste).

**Visualisierung in der Topologie:** Jedes aktive Egress-Profil erscheint als
eigener Knoten (`[VPS] → [Privacy-VPN] → [Internet]` parallel zu
`[VPS] → [Internet direkt]`), mit Traffic-Anteil als Kantenbreite — Wiederverwendung
des in dieser Session gebauten `bps`-proportionalen Edge-Renderings.

## 5. Backend-Architektur

```
services/
  routing/
    egress_service.py     # EgressProfile/EgressRule CRUD + Anwenden
    ingress_service.py     # Ablöse von shorewall_service.py's Forward-Teil
    policy_renderer.py     # Regeln → Shorewall-Zeilen / ip rule / iptables mangle
    conflict_checker.py    # Überlappungsprüfung vor dem Schreiben
    simulator.py           # Trockene Pfad-Berechnung für /routing/simulate
```

`policy_renderer.py` ist der einzige Ort, der System-Kommandos ausführt
(`shorewall check/restart`, `ip rule`, `ip route`, `wg-quick`) — gleiches
Muster wie heute in `shorewall_service._apply()`. Damit bleibt das
Sicherheits-/Validierungs-Review auf eine Datei konzentriert.

**Persistenz:** wie bei `qos.py`/`dns.py` als JSON-State-Datei im
`data_dir` für die Dashboard-eigene Sicht; die tatsächliche Wirkung läuft
weiterhin über die bestehenden Sentinel-Block-Mechanismen in den echten
Systemkonfigurationsdateien (Shorewall-Regeln, `/etc/wireguard/*.conf`,
eine neue `/etc/iproute2/rt_tables`-Erweiterung für die zusätzlichen
Routing-Tabellen).

## 6. Risiken & offene Fragen

- **fwmark/Tabellen-Erschöpfung**: Anzahl gleichzeitiger Egress-Profile sinnvoll
  begrenzen (z. B. UI-Limit 8), um Konflikte mit OMR-eigenen Marks/Tabellen
  zu vermeiden — vorab mit den von OMR selbst genutzten fwmark-Bereichen
  abgleichen (Recherche in `mptcp.sh`/`omr-service` nötig, bevor Tabellen-IDs
  fest vergeben werden).
- **Domain-Matching ist DNS-basiert, nicht paketinhaltsbasiert** — wie im
  bestehenden `omr-dscp`-Mechanismus auch: ein Eintrag wirkt erst nach DNS-
  Auflösung über den Router und nur für IPs, die dabei in das zugehörige
  ipset einsortiert wurden. Muss im UI klar kommuniziert werden (kein SNI-
  Sniffing, kein DPI).
- **IPv6**: `EgressRule`/`IngressRule` werden von Anfang an mit optionalem
  `ip_version`-Feld geplant, auch wenn Phase 1 nur IPv4 ausliefert, um eine
  spätere Breaking Change zu vermeiden.
- **Interaktion mit MPTCP-Scheduler**: Policy-Routing wirkt auf VPS-Seite
  *nach* dem Tunnel; die Wahl, über welchen WAN ein Subflow läuft, bleibt
  Sache des Routers/Schedulers. Das Egress-Profil-Feld `src_link` bezieht sich
  daher auf den ursprünglichen WAN-Tag im Tunnel-Metadatum, nicht auf eine
  direkte Kontrolle des Schedulers selbst — das muss im UI klar getrennt von
  `/protocols` (Scheduler-Einstellungen) dargestellt werden, um keine falschen
  Erwartungen zu wecken.
- **Migrations-Kompatibilität**: bestehende `_demo_forwards`/`ExitVpn`-JSON-
  Dateien müssen beim ersten Start nach Upgrade automatisch in genau eine
  `IngressRule` bzw. ein `EgressProfile` + eine Default-`EgressRule`
  überführt werden (One-Time-Migration in `routing_service.__init__`).

## 7. Serverseitige Anpassungen — Bestandsaufnahme & Lücken

Dieser Abschnitt trennt explizit, was reine Dashboard-Arbeit ist (Backend-
Service + Frontend, beides in diesem Repo) von dem, was tatsächlich auf dem
VPS-System, im Router-Firmware-Repo (`congp20/openmptcprouter`) oder im
upstream `omr-admin` (`Ysurac/openmptcprouter-vps-admin`) angepasst werden
muss — das war im bisherigen Plan implizit, wird hier konkret.

### 7.1 VPS-seitig (Betriebssystem-Ebene, außerhalb von Docker)

| Änderung | Warum nötig | Wo |
|---|---|---|
| Zusätzliche `ip rule`/`ip route`-Tabellen pro Egress-Profil | Mehrere gleichzeitige Exit-Pfade (Abschnitt 3.1) | neu: `policy_renderer.py` führt `ip route`/`ip rule` aus, Tabellen-IDs in `/etc/iproute2/rt_tables` registrieren |
| Mehrere `wg-quick`-Interfaces (`omr-exit-<id>`) statt nur `omr-exit` | ein Interface pro Egress-Profil | Erweiterung von `wireguard_service.py`, eigene `.conf`-Dateien pro Profil |
| `iptables -t mangle` Markierungsregeln (fwmark) | Pakete den `EgressRule`-Bedingungen zuordnen, bevor Policy-Routing greift | neu: `policy_renderer.py` |
| Shorewall: Portbereiche, `statistic`-Match für Lastverteilung, Quell-CIDR-Spalte, `tcrules` für Rate-Limit | Ingress-Granularität (Abschnitt 3.2) | Erweiterung von `shorewall_service.py`, ggf. zusätzliche Shorewall-Konfigdateien (`tcrules`) statt nur `rules` |
| `shorewall check` als Preflight vor `restart` | Trockenlauf-Prinzip (Leitprinzip 3) | `shorewall_service._apply()` |
| Persistente, **verschlüsselte** Konfigurationsablage für Secrets, die heute nur als Klartext-Env-Var existieren (`omr_admin_key`, `router_pass`, `jwt_secret`) | Voraussetzung für Abschnitt 10 (nachträgliche Änderbarkeit) | neuer `settings_service.py`, gleiches AES-256-GCM-Muster wie `backup_service.py` |

### 7.2 Router-seitig (LuCI/UCI/OpenWrt, Repo `congp20/openmptcprouter`)

Diese Punkte sind **keine Dashboard-Codeänderung**, sondern betreffen das
Router-Firmware-Repo — werden hier aufgeführt, weil sie Voraussetzung für
Dashboard-Features sind:

| Änderung | Warum nötig | Aufwand |
|---|---|---|
| `network.lan.dhcp.ignore` per ubus/UCI aus dem Dashboard heraus setzbar | DHCP-Server an/aus für den "Eigene Firewall im LAN"-Modus (Abschnitt 9) | klein — `router_proxy.py` braucht nur einen neuen `uci_set`-Aufruf, UCI-Schema existiert in OpenWrt bereits |
| Neues "WAN-Passthrough"-Interface-Konzept (eigenes Netzwerk-Segment ohne NAT/Firewalling Richtung LAN) | echtes IP-Passthrough einer zusätzlichen öffentlichen IP/Präfix zur Firewall (Abschnitt 9.3, Stufe 3) | **groß** — echte Firmware-/UCI-Schema-Änderung, eigenes Vorhaben im Router-Repo, nicht Teil dieses Dashboard-Plans |
| NDP-Proxy/Routed-/64-Weiterleitung für IPv6-Präfix-Delegation | IPv6-Passthrough zur Firewall (pragmatischere Variante von Stufe 3) | mittel — bestehende OpenWrt-Pakete (`odhcpd`, `ndppd`) lassen sich per UCI ansteuern, aber Dashboard muss diese UCI-Sektion kennen und schreiben können |
| LuCI-Menüeintrag „OMR Dashboard" | reine Erreichbarkeits-Komfortfrage, unabhängig von diesem Plan | bereits in der ursprünglichen Projektplanung als offener Punkt vermerkt |

### 7.3 Upstream `omr-admin` (Repo `Ysurac/openmptcprouter-vps-admin`)

Für reines Editieren bestehender Werte (Abschnitt 10) ist **keine** Änderung
an `omr-admin.py` nötig — das Dashboard spricht es bereits über
`OmrProxy`/Port 65500 an. Erst wenn das granulare Egress-Modell (Abschnitt 3.1)
*mehrere* aktive Protokoll-Instanzen gleichzeitig auf dem VPS verlangt (z. B.
Glorytun TCP *und* ein zweiter, unabhängiger Tunnel für ein zweites
Egress-Profil), müsste geprüft werden, ob `omr-admin` das überhaupt zulässt
— heute ist pro VPS genau ein aktives Tunnelprotokoll vorgesehen
(`OmrProxy.switch_protocol`). **Das ist eine offene Abhängigkeit, kein
gelöstes Problem** — ggf. muss das granulare Egress-Routing zunächst auf
*einen* Tunnel beschränkt bleiben und nur die VPS-seitige *Weiterleitung nach
dem Tunnel* (also reines Exit-Routing der schon gebündelten Verbindung)
granular werden, nicht der Tunnel-Layer selbst. Diese Einschränkung gehört in
die UI-Texte, damit keine falschen Erwartungen entstehen.

### 7.4 Install-Script (`debian12-x86_64.sh`)

Bekannte, bisher nur dokumentierte (nicht behobene) Lücke: das Script
schreibt `ROUTER_PASS=` immer leer in die generierte `.env` (siehe Zeile
~1172), weil das Router-Passwort zum Zeitpunkt der VPS-Installation meist
noch nicht bekannt ist (der Router existiert ja oft noch nicht). Zwei
Verbesserungen, beide klein:

1. Interaktive Abfrage am Script-Ende: *"Router-Passwort jetzt eintragen?
   (kann später im Dashboard nachgeholt werden) [j/N]"*.
2. Deutlicherer Hinweis direkt in der Script-Ausgabe (nicht nur in
   `INSTALL.de.md`), z. B. `echo`-Zeile direkt nach dem Start des Containers.

Mit der in Abschnitt 10 geplanten Settings-Seite wird Punkt 1 ohnehin
entschärft — das Passwort lässt sich dann bequem im Dashboard nachtragen,
ohne `.env` händisch zu editieren und Container neu zu starten.

## 8. Nachträgliche Änderbarkeit — Audit aller Wizard-Werte

Konkrete Umsetzung von Leitprinzip 7. Heutiger Stand pro Wert:

| Wert | Heute nachträglich änderbar? | Geplante Lösung |
|---|---|---|
| VPS-IP | Nur einmalig im Wizard; wird ins Router-UCI geschrieben, nicht im Dashboard selbst gespeichert | Neue „Verbindung"-Karte unter `/system`: Feld erneut bearbeitbar, „Erneut anwenden" schreibt erneut ins Router-UCI (ruft intern dieselbe Logik wie `wizard.apply` Schritt 2 auf) |
| `OMR_ADMIN_KEY` | Nur über `.env` + Container-Neustart | Settings-Seite, **sofort wirksam** ohne Neustart: Wert landet in der neuen verschlüsselten Settings-Ablage, `get_settings.cache_clear()` plus `os.environ`-Update reicht, da nur als HTTP-`Authorization`-Header verwendet |
| `ROUTER_IP` / `ROUTER_USER` / `ROUTER_PASS` | Nur über `.env` + Container-Neustart | Settings-Seite mit **Verbindungstest-Button** (ruft `wizard.detect_wans` testweise auf, bevor gespeichert wird) — sofort wirksam wie oben |
| Tunnelprotokoll | ✅ bereits über `/protocols` änderbar | — |
| WAN-Label/Typ/Priorität | ✅ bereits über `/links` änderbar | — |
| LAN-IP / DHCP-Bereich | Nur im Wizard gesetzt, danach in keiner Dashboard-Seite mehr sichtbar oder editierbar | Neue Karte „Netzwerk" unter `/system` (oder eigene `/network`-Seite), schreibt erneut per `uci_set` auf den Router |
| Exit-VPN | ✅ bereits über `/vps` änderbar | — |
| Port-Weiterleitungen | ✅ bereits über `/vps` änderbar | — |
| `JWT_SECRET` | Nur über `.env` + Neustart | Settings-Seite „Sicherheit"; **mit Warnhinweis**, dass ein Wechsel alle aktiven Dashboard-Sessions abmeldet — ehrlich anzeigen, nicht verschleiern |
| `DASHBOARD_PASS` | Nur über `.env` + Neustart | Settings-Seite „Sicherheit", sofort wirksam |
| `BIND_ADDR` | Nur über `.env` + `docker compose up -d` (Netzwerkbindung) | Settings-Seite zeigt aktuellen Wert + **klaren Hinweis „erfordert Container-Neustart"** statt eines falschen Live-Apply-Eindrucks; optional ein „Neustart jetzt ausführen"-Button, der intern `docker compose restart` auslöst (setzt Docker-Socket-Zugriff aus dem Backend-Container voraus — Sicherheitsabwägung, siehe Risiken) |

**Architektur-Konsequenz:** `config.py`s `Settings` bleibt die *Default*-Quelle
(aus Env-Vars beim Start), bekommt aber einen Override-Layer: ein neuer
`settings_service.py` liest/schreibt eine verschlüsselte JSON-Datei im
`data_dir` (Muster wie `backup_service.py`), die beim Start *nach* den
Env-Defaults geladen wird und diese überschreibt. Jede Änderung über die neue
Settings-API aktualisiert sowohl diese Datei als auch `.env` (für
Persistenz über einen Container-Neustart hinweg) und ruft
`get_settings.cache_clear()` auf. `BIND_ADDR`/Ports bleiben die einzige
ehrliche Ausnahme, die einen Neustart braucht.

## 9. Eigene Firewall hinter dem OMR-Router

### 9.1 Problemstellung

Praxis-Realität: kaum jemand betreibt den OMR-Router als alleinigen
Heimnetz-Router mit eigenem DHCP für alle Endgeräte. Üblich ist, den
OMR-Router als reine „Bonding-Bridge" zu betreiben und die eigentliche
Firewall (OPNsense/pfSense/Sophos/Fritzbox o. ä.) mit ihrem **WAN-Port** an
einen LAN-Port des OMR-Routers anzuschließen. Damit entsteht IMMER eine Form
von Doppel-NAT: der OMR-Router NAT't (über den VPS) ins Internet, die
Firewall NAT't zusätzlich für ihr eigenes LAN. Die Firewall „sieht" als ihre
WAN-IP nur die private OMR-LAN-Adresse, nicht die echte öffentliche IP des
VPS — das verwirrt z. B. DDNS-Anzeigen, Site-to-Site-VPN-Konfiguration und
jede Funktion, die „meine öffentliche IP" voraussetzt.

### 9.2 Direkte Antwort: Kann die VPS-IP an die Firewall übertragen werden?

**Ja, aber in drei Ausbaustufen mit sehr unterschiedlichem Aufwand:**

**Stufe 1 — Doppel-NAT bewusst akzeptieren, aber sauber konfigurieren
(heute schon möglich, nur UI/Doku-Arbeit).** OMR-DHCP am LAN-Port deaktivieren,
Firewall bekommt eine statische IP im OMR-LAN-Subnetz (Punkt-zu-Punkt-artig,
z. B. `192.168.100.1` Router / `192.168.100.2` Firewall). Funktioniert
zuverlässig, ändert aber nichts an der „falschen" WAN-IP-Anzeige der Firewall
selbst.

**Stufe 2 — Aufklären statt bauen (kein Code, nur Info-Banner).** Der
naheliegende Schmerzpunkt — „meine Firewall zeigt die falsche WAN-IP, DDNS
funktioniert bestimmt nicht" — stimmt in der Praxis meist **nicht**: die
meisten Firewall-Betriebssysteme ermitteln ihre „öffentliche IP" für DDNS
nicht von der eigenen (privaten) WAN-Schnittstelle, sondern fragen einen
externen Check-Dienst ab (z. B. `checkip.dyndns.org`, viele DDNS-Clients haben
einen „IP automatisch über Internet-Dienst ermitteln"-Modus). Dieser Dienst
sieht zwangsläufig die **echte VPS-Public-IP**, weil das die Adresse ist, mit
der der gebündelte Traffic tatsächlich das Internet erreicht. DDNS auf der
Firewall funktioniert in diesem Modus also bereits **ohne jede Änderung**.
Das Dashboard sollte das nur sichtbar machen: ein Info-Hinweis auf `/vps`
("Deine Firewall zeigt vermutlich eine private WAN-IP — das ist normal.
Deine tatsächliche öffentliche IP ist: `<aktuelle VPS-Public-IP>`, nutze den
Modus 'externe IP-Ermittlung' für DDNS auf deiner Firewall.").

**Stufe 3 — Echtes IP-Passthrough (substanzielle Neuentwicklung, eigenes
Vorhaben).** Eine zusätzliche öffentliche IPv4-Adresse (oder ein /29-Block)
bzw. ein IPv6-/64-Präfix zusätzlich zur Haupt-IP des VPS beim Hoster
beantragen und diese **unverändert, ohne NAT, ohne Shorewall-DNAT** durch den
Tunnel bis zur Firewall durchrouten — die Firewall bekommt dann eine
*tatsächliche* öffentliche IP auf ihrer WAN-Schnittstelle, exakt wie an einem
klassischen Modem/ONT. Technisch nötig:

- VPS-seitig: `ip route` für die zusätzliche IP/Subnetz über das
  Tunnel-Interface zur Tunnel-IP des Routers (kein NAT/Masquerading für
  diese Adresse).
- Router-seitig (echte Firmware-Änderung im `openmptcprouter`-Repo, **nicht**
  Teil dieses Dashboard-Plans): ein neues Konzept "WAN-Passthrough-Port" —
  ein LAN-Port, der die durchgereichte IP unverändert weitergibt, statt sie
  zu NATen/zu firewallen. Entweder als eigenes VLAN/Transfer-Subnetz
  (empfohlen, kein Hack nötig) oder per Proxy-ARP, falls Firewall und andere
  Geräte im selben L2-Segment bleiben müssen.
- **IPv6 ist der pragmatischere Einstieg**: die meisten VPS-Hoster vergeben
  großzügige `/64`- oder `/48`-Präfixe ohnehin kostenlos, und natives,
  NAT-freies Routing eines `/64` per Präfix-Delegation (`odhcpd`/`ndppd`,
  bereits in OpenWrt vorhanden) ist deutlich weniger invasiv als echtes
  IPv4-Passthrough.

| Stufe | Aufwand | Voraussetzung | Ergebnis |
|---|---|---|---|
| 1 | klein (Dashboard-UI/Doku) | keine | Doppel-NAT, aber stabil und dokumentiert |
| 2 | sehr klein (Info-Banner) | keine | DDNS/„meine IP"-Funktionen der Firewall funktionieren bereits korrekt — nur sichtbar machen |
| 3 | groß (Firmware-Änderung + zusätzliche IP/Präfix vom Hoster) | eigenes Vorhaben, vermutlich eigener Plan im Router-Repo `congp20/openmptcprouter` | echtes NAT-freies Passthrough, wie ein klassisches Modem |

### 9.3 Weitere Features für den Einsatz mit eigener Firewall

- **Preset „Eigene Firewall / eigenes NAT"** im Wizard-Schritt 5
  (LAN-Konfiguration): deaktiviert automatisch den OMR-DHCP-Server und
  schlägt eine Punkt-zu-Punkt-Adressierung vor, statt dass der Nutzer das
  manuell in LuCI nachvollziehen muss.
- **UPnP/NAT-PMP-Relay-Dienst**: nimmt SSDP/UPnP-IGD-Anfragen von Geräten
  hinter der Firewall entgegen (muss vom Router durchgeleitet werden — kleine
  router-seitige Anpassung nötig, siehe 7.2) und übersetzt sie automatisch in
  `IngressRule`s auf dem VPS. Damit funktionieren Spielekonsolen/
  Torrent-Clients hinter der eigenen Firewall ohne manuelle Port-Weiterleitung
  im Dashboard — genau das, was ein normaler Heimrouter "automatisch" macht,
  hier eben am VPS nachgebildet.
- **Firewall als eigener Topology-Knoten mit Health-Check**: automatischer
  Ping/Erreichbarkeits-Check der konfigurierten Firewall-IP, sichtbar als
  Knoten in der Topologie (analog zum bestehenden NAS/Server-Knoten-Muster),
  farbcodiert nach Status.
- **MTU-Empfehlung berücksichtigt den zusätzlichen Hop**: das im
  Ursprungsplan vorgesehene MTU-Finder-Tool muss bei aktiviertem
  "Eigene Firewall"-Preset den zusätzlichen Kapselungs-/NAT-Hop einrechnen,
  da die Firewall selbst nochmal fragmentieren/kapseln kann — sonst wird eine
  MTU empfohlen, die am Endgerät hinter der Firewall wieder zu groß ist.
- **Bestehendes „Firewall/VPN-Durchleitung"-Ingress-Preset bewusst
  hervorheben**: das in der ursprünglichen Projektplanung bereits vorgesehene
  Preset für eingehende VPN-Verbindungen (z. B. eigenes WireGuard/IPsec der
  Firewall, Port 500/4500/51820 → Firewall-LAN-IP) ist hier der zentrale
  Baustein für eingehende Verbindungen zur Firewall selbst — keine neue
  Arbeit nötig, aber im neuen `/routing`-UI (Abschnitt 4) als „Für
  Firewall-Betrieb empfohlen" markieren, damit Nutzer es finden.
- **DHCP nicht nur an/aus, sondern eingeschränkt**: für den Fall, dass
  trotz eigener Firewall noch ein einzelnes Gerät direkt am OMR-Router
  betrieben werden soll (z. B. ein IoT-Gerät), DHCP nicht komplett
  deaktivieren, sondern auf einen reduzierten Adressbereich begrenzen können
  — kleine Erweiterung des LAN-Konfig-Schritts.

## 10. Phasenplan (Umsetzung, falls beschlossen)

0. **Phase R0 — Settings-Service & Nachträgliche Änderbarkeit**: neuer
   `settings_service.py` (verschlüsselte Override-Ablage + `.env`-Sync +
   Cache-Invalidierung), neue Settings-Seite im Frontend (Verbindung,
   Sicherheit, Netzwerk), Verbindungstest-Buttons. **Voraussetzung für alles
   Weitere** — sollte vor R1 kommen, da spätere Phasen (mehrere Egress-Profile,
   Router-UCI-Schreibzugriffe) ohnehin von einer robusten Settings-Schicht
   profitieren.
1. **Phase R1 — Datenmodell & Migration**: neue Schemas, JSON-Persistenz,
   automatische Migration der bestehenden `PortForward`/`ExitVpn`-Daten,
   `/routing/*`-Endpunkte parallel zu den bestehenden (noch ohne UI).
2. **Phase R2 — Ingress-Granularität**: Portbereiche, Mehrfachziele mit
   Lastverteilung, Quell-CIDR-Filter, Rate-Limit — Erweiterung von
   `shorewall_service.py`/`policy_renderer.py`, UI-Tabelle erweitert.
3. **Phase R3 — Mehrere Egress-Profile**: zweites/drittes WireGuard-Exit-
   Interface, `ip rule`/`ip route`-Tabellen, fwmark-Vergabe, einfache
   Default-Regel pro Profil (noch ohne Matching-UI).
4. **Phase R4 — Egress-Regel-Engine**: `EgressMatch`-Bedingungen, Prioritäten,
   Konfliktprüfung, Regel-Editor-UI, Topologie-Integration (Profil-Knoten).
5. **Phase R5 — Simulator & Vorschau**: `/routing/simulate`, Vorschau-Text vor
   dem Anwenden, Zeitfenster-Bedingungen.
6. **Phase R6 — Sicherheits-Review & Doku**: vollständiger Threat-Review der
   neuen Angriffsfläche (insbesondere 1:1-Host-Exposure und Rate-Limit-
   Umgehung), Aktualisierung von `config-map` und `INSTALL.de.md`.
7. **Phase R7 — Eigene Firewall, Stufe 1+2**: DHCP-Toggle-Preset, Info-Banner
   zur VPS-Public-IP/DDNS-Erklärung, Firewall-Topology-Knoten mit Health-Check,
   UPnP/NAT-PMP-Relay (sofern Router-seitige Durchleitung vorbereitet ist).
8. **Phase R8 — Eigene Firewall, Stufe 3 (IP-Passthrough)**: eigenes,
   größeres Vorhaben mit Abhängigkeit zum Router-Firmware-Repo
   (`congp20/openmptcprouter`) und zur Hoster-IP-Vergabe; verdient einen
   eigenen Plan/Issue, sobald R7 abgeschlossen ist und echter Bedarf
   bestätigt wurde.

## 11. Verifikation (pro Phase)

- `pytest dashboard/backend/tests/test_routing*.py` für Renderer- und
  Konflikt-Logik (reine Übersetzungs-/Validierungslogik, gut testbar ohne
  echten VPS).
- Manuelle Demo-Verifikation wie bei den bisherigen Features: Backend im
  `OMR_DASHBOARD_DEMO=true`-Modus, Playwright-Durchlauf über `/routing`
  (Regel anlegen, Konfliktmeldung bei Überlappung provozieren, Simulator
  abfragen, Topologie-Knoten für neues Profil prüfen).
- Auf einer echten VPS-Testinstanz: `ip rule list` / `ip route show table
  <n>` / `shorewall show rules` nach Anwenden gegen die im UI angezeigte
  Vorschau abgleichen.
- **R0 zusätzlich**: nach jeder Settings-Änderung per UI prüfen, dass *kein*
  Container-Neustart nötig war (außer den dokumentierten Ausnahmen wie
  `BIND_ADDR`) — z. B. `ROUTER_PASS` ändern und sofort einen
  Verbindungstest auslösen, ohne `docker compose restart`.
- **R7 zusätzlich**: DHCP-Toggle setzen → prüfen, dass der Router tatsächlich
  keine Leases mehr vergibt (`ubus call dhcp ipv4leases` o. ä.); Info-Banner
  mit der echten VPS-Public-IP gegen `curl ifconfig.me` auf dem VPS
  abgleichen.
