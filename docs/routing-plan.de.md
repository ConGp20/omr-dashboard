# Plan: Granulares Egress- & Ingress-Routing

Status: **Planungsdokument, nicht implementiert.** Beschreibt die Erweiterung
des heutigen, bewusst simplen Routing (1 Exit-VPN, 1 Domain-Liste, 1 DNAT pro
Port) zu einem granularen Policy-Routing-System für ein- und ausgehenden
Verkehr am VPS-Endpunkt. Dient als Grundlage für eine spätere
Implementierungs-Phase (siehe `Phasenplan` unten); keine Codeänderung in
diesem Schritt.

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

## 7. Phasenplan (Umsetzung, falls beschlossen)

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

## 8. Verifikation (pro Phase)

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
