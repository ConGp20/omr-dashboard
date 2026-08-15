# OMR Dashboard — Ausführliche Installationsanleitung

Diese Anleitung führt Dich von Null bis zum laufenden Dashboard. Sie ist in vier
Wege gegliedert — wähle den, der zu Dir passt:

- **[Weg 0 — Demo zuerst ausprobieren](#weg-0--demo-zuerst-ausprobieren)** (kein VPS nötig, 2 Minuten)
- **[Weg 1 — Automatisch über das VPS-Install-Script](#weg-1--automatisch-über-das-vps-install-script)** (empfohlen)
- **[Weg 2 — Manuell mit Docker Compose](#weg-2--manuell-mit-docker-compose)**
- **[Weg 3 — Ohne Docker, direkt mit Python + Node](#weg-3--ohne-docker-direkt-mit-python--node)** (Entwicklung/Debug)

Danach: **[Der Einrichtungs-Wizard Schritt für Schritt](#der-einrichtungs-wizard-schritt-für-schritt)**,
**[Zugriff absichern](#zugriff-absichern-tunnel-statt-öffentlich)**,
**[Fehlersuche](#fehlersuche)**, **[Update / Backup](#update--backup)** und
**[Eigene Firewall hinter dem OMR-Router](#eigene-firewall-hinter-dem-omr-router-einrichten)**.

---

## Komplettanleitung in 12 Schritten (Kurzfassung)

Wer einfach der Reihe nach klicken/tippen will, ohne erst alle Abschnitte zu
lesen — die folgenden 12 Schritte sind der vollständige Weg von einem leeren
VPS bis zum laufenden Dashboard samt Router. Jeder Schritt verlinkt auf den
ausführlichen Abschnitt, falls etwas schiefgeht.

1. **VPS mit OpenMPTCProuter-VPS-Komponente installieren** (falls noch nicht
   geschehen) — das normale OMR-VPS-Install-Script, unabhängig vom Dashboard.
   Danach läuft `omr-admin` auf Port 65500 und es existiert
   `/root/openmptcprouter_config.txt` mit dem **Server-Key**.
2. **Server-Key notieren**: `cat /root/openmptcprouter_config.txt` auf dem
   VPS — diesen Wert brauchst Du in Schritt 7 (Wizard) als „omr_key".
3. **Dashboard mitinstallieren**, im selben Verzeichnis wie
   `debian12-x86_64.sh` auf dem VPS:
   ```bash
   DASHBOARD=yes DASHBOARD_BIND=127.0.0.1 ./debian12-x86_64.sh
   ```
   → Details: [Weg 1](#weg-1--automatisch-über-das-vps-install-script).
4. **⚠️ `ROUTER_PASS` sofort prüfen.** Das Script schreibt diesen Wert immer
   leer in `/opt/openmptcprouter-vps/dashboard/.env`, weil der Router beim
   VPS-Setup meist noch nicht existiert. Live-Linkmetriken vom Router
   funktionieren erst, wenn Du ihn nachträgst (Schritt 9). Das ist normal —
   nicht abbrechen, einfach merken und später erledigen.
5. **Per SSH-Tunnel auf das Dashboard zugreifen** (der WireGuard-Management-
   Tunnel existiert noch nicht, solange kein Router verbunden ist):
   ```bash
   ssh -L 3000:127.0.0.1:3000 root@<VPS-IP>
   ```
   Dann im Browser: `http://localhost:3000`.
6. **Router (OpenMPTCProuter-Image) aufsetzen/flashen und ins LAN des VPS-
   Zugangs hängen**, falls noch nicht geschehen — eigener, OMR-Router-
   spezifischer Schritt, nicht Teil des Dashboards.
7. **Wizard Schritt 1–2**: „Neu einrichten" wählen, VPS-IP/Domain +
   Server-Key (aus Schritt 2) eingeben, **Verbindung testen**.
8. **Wizard Schritt 3**: Router-IP (Standard `192.168.100.1`),
   LuCI-Benutzer (`root`) und das **aktuelle Router-Passwort** eingeben →
   **Leitungen erkennen**. Erkannte WANs benennen, Typ zuweisen.
9. **`ROUTER_PASS` jetzt in der `.env` nachtragen** (das Passwort aus
   Schritt 8 kennst Du jetzt):
   ```bash
   cd /opt/openmptcprouter-vps/dashboard
   nano .env        # ROUTER_PASS=<dein-LuCI-Passwort>
   docker compose up -d
   ```
   Ohne diesen Schritt zeigt das Dashboard Leitungen ohne Live-Metriken an.
10. **Wizard Schritt 4–6**: Protokoll wählen, LAN-Konfiguration bestätigen,
    **Jetzt verbinden** → Tunnel wird aufgebaut, kurzer Geschwindigkeitstest.
11. **Zugriff dauerhaft absichern**: sobald der Tunnel steht, `BIND_ADDR` in
    der `.env` auf die WireGuard-Management-Tunnel-IP setzen (statt
    `127.0.0.1`/SSH-Tunnel) → [Zugriff absichern](#zugriff-absichern-tunnel-statt-öffentlich).
12. **Optional: eigene Firewall statt OMR-DHCP** — falls Du (wie die meisten)
    eine eigene Firewall mit ihrem WAN-Port an den OMR-Router anschließt →
    [Eigene Firewall hinter dem OMR-Router einrichten](#eigene-firewall-hinter-dem-omr-router-einrichten).

---

## Konzept in einem Absatz

Das Dashboard läuft **auf dem VPS** als Docker-Sidecar neben dem bestehenden
`omr-admin`-Dienst. Es besteht aus zwei Containern: einem **Backend** (FastAPI,
Port 65501, nur lokal) und einem **Frontend** (Next.js, Port 3000). Der Browser
spricht ausschließlich mit dem Frontend; dieses leitet serverseitig an das
Backend weiter — so bleibt das Backend (und der Admin-Key) vom öffentlichen Netz
fern. Der Router bleibt unverändert, LuCI bleibt erreichbar.

```
Browser ──/api──▶ Frontend (Next.js :3000) ──▶ Backend (FastAPI :65501)
                                                   ├─▶ omr-admin   (127.0.0.1:65500, HTTPS)
                                                   ├─▶ Router LuCI (http://ROUTER_IP/ubus)
                                                   └─▶ Shorewall / WireGuard (lokal auf dem VPS)
```

---

## Voraussetzungen

| Was | Wofür | Pflicht |
|-----|-------|---------|
| VPS mit installiertem OpenMPTCProuter-VPS (`omr-admin` läuft auf 65500) | Datenquelle | für Live-Betrieb |
| Docker + Compose-Plugin | Container-Betrieb | Weg 1 & 2 |
| ~1–2 GB freier RAM zur Build-Zeit | Next.js-Build | Weg 1 & 2 |
| Router mit OpenMPTCProuter, erreichbar im LAN | WAN-Erkennung, Live-Metriken | für vollständige Funktion |
| Server-Key des VPS (aus `/root/openmptcprouter_config.txt`) | Auth gegen omr-admin | für Live-Betrieb |
| Router-LuCI-Passwort | WAN-Erkennung + Link-Metriken | für Router-Daten |

> **Nur mal anschauen?** Dann brauchst Du **nichts** davon — nimm Weg 0 (Demo).

---

## Weg 0 — Demo zuerst ausprobieren

Synthetische Daten, kein VPS, kein Router. Ideal um die UI vorab zu sehen.

```bash
cd dashboard
docker compose -f docker-compose.dev.yml up
# Browser: http://localhost:3000
```

Der Backend-Container läuft mit `OMR_DASHBOARD_DEMO=true`, das Frontend mit
Hot-Reload. Du kannst den kompletten Wizard, das Dashboard (BONDED/DEGRADED),
Topologie, Port-Weiterleitungen, Exit-VPN usw. durchklicken — alles mit
glaubwürdigen Fantasiedaten.

Beenden: `Strg+C`, danach optional `docker compose -f docker-compose.dev.yml down`.

---

## Weg 1 — Automatisch über das VPS-Install-Script

Das VPS-Install-Script kann das Dashboard direkt mitinstallieren. Es installiert
bei Bedarf Docker, kopiert die Quellen nach `/opt/openmptcprouter-vps/dashboard`,
schreibt die `.env` aus den generierten Zugangsdaten und startet den Stack.

```bash
# Auf dem VPS, im Verzeichnis mit debian12-x86_64.sh:
DASHBOARD=yes DASHBOARD_BIND=127.0.0.1 ./debian12-x86_64.sh
```

**Flags:**

| Flag | Bedeutung | Default |
|------|-----------|---------|
| `DASHBOARD=yes` | Dashboard mitinstallieren | `no` |
| `DASHBOARD_BIND=<IP>` | Bind-Adresse des Frontends | `127.0.0.1` |

Nach Abschluss meldet das Script:

```
OMR Dashboard reachable at http://127.0.0.1:3000 (through the router tunnel)
```

Die erzeugte `.env` liegt in `/opt/openmptcprouter-vps/dashboard/.env`. Sie wird
so befüllt:

```
OMR_DASHBOARD_DEMO=false
OMR_ADMIN_KEY=<Server-Key des VPS>          # = OMR_ADMIN_PASS
ROUTER_IP=192.168.100.1
ROUTER_USER=root
ROUTER_PASS=                                 # ⚠️ LEER — siehe unten
BIND_ADDR=127.0.0.1
DASHBOARD_PASS=<Admin-Passwort>              # = OMR_ADMIN_PASS_ADMIN
JWT_SECRET=<zufällig generiert>
```

> ⚠️ **Wichtig: `ROUTER_PASS` ist zunächst leer.** Der Wizard fragt das
> Router-Passwort interaktiv für die WAN-Erkennung ab, aber der Hintergrund-Poller
> (Live-Link-Metriken direkt vom Router) nutzt den Wert aus der `.env`. Sobald der
> Router steht, das Passwort eintragen und neu starten:
>
> ```bash
> cd /opt/openmptcprouter-vps/dashboard
> nano .env                       # ROUTER_PASS=<dein-LuCI-Passwort>
> docker compose up -d            # übernimmt die neue .env
> ```

Weiter mit **[Zugriff absichern](#zugriff-absichern-tunnel-statt-öffentlich)** und
dem **[Wizard](#der-einrichtungs-wizard-schritt-für-schritt)**.

---

## Weg 2 — Manuell mit Docker Compose

Wenn Du das Dashboard getrennt vom Install-Script aufsetzt:

```bash
cd dashboard
cp .env.example .env
nano .env                        # Werte setzen (siehe Tabelle unten)
docker compose up -d --build     # baut beide Images und startet sie
```

**`.env`-Referenz:**

| Variable | Bedeutung | Beispiel / Hinweis |
|----------|-----------|--------------------|
| `OMR_DASHBOARD_DEMO` | Demo-Modus | `false` im Echtbetrieb |
| `OMR_ADMIN_KEY` | Server-Key des VPS, Auth gegen omr-admin | aus `/root/openmptcprouter_config.txt` |
| `ROUTER_IP` | LAN-IP des Routers | `192.168.100.1` |
| `ROUTER_USER` | LuCI-Benutzer | `root` |
| `ROUTER_PASS` | LuCI-Passwort | für Live-Router-Metriken nötig |
| `BIND_ADDR` | Bind-Adresse des Frontends | Erstlauf `127.0.0.1`, später Tunnel-IP |
| `DASHBOARD_PASS` | Login-Passwort fürs Dashboard | leer ⇒ fällt auf `OMR_ADMIN_KEY` zurück |
| `JWT_SECRET` | Signierschlüssel für Sessions | **unbedingt** lange Zufallszeichenkette |

Einen starken `JWT_SECRET` erzeugen:

```bash
od -vN 32 -An -tx1 /dev/urandom | tr -d ' \n'; echo
```

Status prüfen:

```bash
docker compose ps
docker compose logs -f            # Live-Logs beider Container
curl -s http://127.0.0.1:65501/health        # Backend: {"status":"ok",...}
curl -sI http://127.0.0.1:3000/              # Frontend: HTTP 200
```

---

## Weg 3 — Ohne Docker, direkt mit Python + Node

Für Entwicklung oder Debugging. Zwei Terminals.

**Backend:**

```bash
cd dashboard/backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

# Demo:
OMR_DASHBOARD_DEMO=true uvicorn omr_dashboard_api:app --port 65501

# Echtbetrieb (Beispiel):
OMR_DASHBOARD_OMR_ADMIN_KEY=<key> \
OMR_DASHBOARD_ROUTER_PASS=<pass> \
OMR_DASHBOARD_JWT_SECRET=<random> \
uvicorn omr_dashboard_api:app --host 127.0.0.1 --port 65501
```

> Hinweis: Direkt am Backend heißen die Variablen mit Präfix
> `OMR_DASHBOARD_…` (siehe `backend/config.py`). Im Docker-Compose werden die
> kürzeren `.env`-Namen (`OMR_ADMIN_KEY` usw.) darauf gemappt.

**Frontend:**

```bash
cd dashboard/frontend
npm install
BACKEND_URL=http://127.0.0.1:65501 npm run dev
# Browser: http://localhost:3000
```

---

## Zugriff absichern: Tunnel statt öffentlich

Das Dashboard gehört **nicht** ins öffentliche Netz. Es soll über den
WireGuard-Management-Tunnel erreichbar sein, den OMR ohnehin aufbaut.

**Henne-Ei beim Erstaufbau:** Der Management-Tunnel (`10.255.247.1`) existiert
erst, nachdem der Router verbunden ist. Deshalb:

**Phase 1 — Erstaufbau (Tunnel existiert noch nicht):**

`BIND_ADDR=127.0.0.1` lassen und per SSH-Tunnel zugreifen:

```bash
# Auf Deinem lokalen Rechner:
ssh -L 3000:127.0.0.1:3000 root@<VPS-IP>
# Dann im Browser: http://localhost:3000
```

**Phase 2 — Nach Router-Verbindung (Tunnel steht):**

```bash
cd /opt/openmptcprouter-vps/dashboard
nano .env                        # BIND_ADDR=10.255.247.1
docker compose up -d
# Erreichbar unter http://10.255.247.1:3000 — von jedem Gerät hinter dem Router
```

Die VPS-Firewall (Shorewall) öffnet die Ports 3000/65501 **nicht** zum Internet;
durch das Host-Binding auf `BIND_ADDR` lauscht der Dienst nur auf der gewählten
(Tunnel-)Adresse.

---

## Der Einrichtungs-Wizard Schritt für Schritt

Beim ersten Aufruf landest Du auf `/wizard`. Sechs Schritte:

| Schritt | Was eingeben / tun | Herkunft |
|---------|--------------------|----------|
| **1 Willkommen** | „Neu einrichten" wählen (oder „Backup wiederherstellen") | — |
| **2 VPS verbinden** | VPS-IP/Domain + Server-Key → **Verbindung testen**. Erfolg zeigt VPS-Version + verfügbare Protokolle | ☁️ VPS |
| **3 Leitungen** | Router-IP + LuCI-Benutzer + Passwort → **Leitungen erkennen**. Erkannte WANs benennen und Typ (Fiber/LTE/5G…) zuweisen | 🖥️ Router |
| **4 Protokoll** | Tunnelprotokoll wählen (Karten mit Klartext-Empfehlungen). Schlüssel wird auf dem VPS erzeugt und automatisch zum Router übertragen | ☁️+🔄 |
| **5 LAN** | Router-LAN-IP + DHCP-Bereich bestätigen (Vorgaben passen meist) | 🖥️ Router |
| **6 Verbinden** | Zusammenfassung prüfen → **Jetzt verbinden**. Das Dashboard aktiviert das Protokoll auf dem VPS, überträgt Keys zum Router, baut den Tunnel auf | — |

Am Ende: **„Geschafft!"** mit aggregierter Geschwindigkeit und Button **„Zum
Dashboard"**.

> **Tipp für den ersten Live-Lauf:** parallel `docker compose logs -f` mitlaufen
> lassen. Schlägt Schritt 2 fehl, prüfe `OMR_ADMIN_KEY` und ob omr-admin auf 65500
> antwortet. Schlägt Schritt 3 fehl, prüfe `ROUTER_IP`/Passwort und ob der Router
> aus Sicht des VPS erreichbar ist.

---

## Fehlersuche

**Container-Status & Logs:**

```bash
cd /opt/openmptcprouter-vps/dashboard
docker compose ps
docker compose logs -f backend
docker compose logs -f frontend
```

**Gesundheits-Checks:**

```bash
curl -s http://127.0.0.1:65501/health        # Backend antwortet?
curl -sI http://<BIND_ADDR>:3000/             # Frontend liefert HTTP 200?
```

| Symptom | Wahrscheinliche Ursache | Lösung |
|---------|------------------------|--------|
| Wizard Schritt 2 „Verbindung fehlgeschlagen" | Falscher `OMR_ADMIN_KEY` oder omr-admin läuft nicht | Key prüfen; `systemctl status omr-admin`; `curl -k https://127.0.0.1:65500/` |
| Schritt 3 erkennt keine Leitungen | Router nicht erreichbar / falsches Passwort | `ROUTER_IP`/`ROUTER_PASS` prüfen; vom VPS aus `curl http://<ROUTER_IP>/ubus` testen |
| Dashboard zeigt Leitungen ohne Live-Metriken | `ROUTER_PASS` in `.env` leer | Passwort setzen, `docker compose up -d` |
| Seite lädt nicht über Tunnel-IP | `BIND_ADDR` noch auf `127.0.0.1` | auf Tunnel-IP setzen, neu starten |
| Build bricht mit Speicherfehler ab | Zu wenig RAM bei `docker compose build` | Swap hinzufügen oder lokal bauen + Image übertragen |
| Status bleibt „OFFLINE" trotz Tunnel | omr-admin `/status`-Form abweichend | `docker compose logs backend` prüfen; Demo zum Vergleich |

**Neu bauen nach Änderungen:**

```bash
docker compose up -d --build
```

---

## Update / Backup

**Dashboard aktualisieren** (neue Quellen geholt):

```bash
cd /opt/openmptcprouter-vps/dashboard
docker compose up -d --build
```

**Konfiguration sichern:** Im Dashboard unter **System → Backup** ein
verschlüsseltes `.omr-backup.json.gz` erzeugen (Passwort wählen — die Tunnel-Keys
werden AES-256-GCM verschlüsselt, nie im Klartext). Wiederherstellen über
**System → Restore** oder direkt im Wizard (Schritt 1 → „Backup wiederherstellen").

Das Backup enthält auch die **Datenlimits** pro WAN und die **Alarm-Konfiguration**
(Bot-Token und SMTP-Passwort liegen im verschlüsselten Teil). Nach einer
Wiederherstellung sind beide sofort wieder aktiv.

---

## Anmeldung

Sobald ein Dashboard-Passwort gesetzt ist (`DASHBOARD_PASS` in der `.env` — das
Install-Script setzt es automatisch), erscheint beim Aufruf eine Anmeldemaske.

- Benutzer ist standardmäßig `admin`, das Passwort steht in der `.env`.
- Ist **kein** Passwort gesetzt (frische Installation) oder läuft das Dashboard
  im Demo-Modus, entfällt die Anmeldung — es gäbe nichts zu prüfen.
- Das Sitzungs-Token liegt in einem httpOnly-Cookie und ist für JavaScript im
  Browser nicht lesbar. Der Server hängt es intern an jede Anfrage.
- Nach fünf Fehlversuchen ist die Anmeldung fünf Minuten gesperrt (pro
  Absender-IP). Passwörter werden zeitkonstant verglichen.
- Abmelden: unten in der Seitenleiste.

Passwort ändern unter **System → Sicherheit**. Wenn Du dort auch das
JWT-Secret änderst, werden alle offenen Sitzungen sofort abgemeldet.

## Systemcheck: Hinweise und Empfehlungen

Die Seite **Systemcheck** prüft die Konfiguration und meldet, was auffällt —
**rein beratend**. Nichts davon blockiert eine Aktion; Du kannst jeden Punkt
ignorieren.

Geprüft werden unter anderem:

| Bereich | Beispiel |
|---|---|
| Sicherheit | JWT-Secret noch der Platzhalter, kein Dashboard-Passwort, `BIND_ADDR` öffentlich erreichbar |
| Verbindung | Kein Tunnel aktiv, nur eine Leitung, Leitung mit hohem Paketverlust/Latenz |
| Datenverbrauch | Mobilfunk-Leitung ohne Limit, Limit fast/ganz erreicht, Hochrechnung überschreitet das Limit |
| Benachrichtigungen | Kein Kanal aktiv, Wiederholsperre abgeschaltet |
| Leistung | Ein anderes Tunnel-Protokoll passt besser zum Leitungsmix |

Jeder Befund nennt **was** auffällt, **warum** das zählt und **was zu tun ist** —
mit Direktlink auf die passende Seite. Auf der Übersicht erscheint zusätzlich
eine dezente Zeile mit dem wichtigsten offenen Punkt; gibt es nichts zu melden,
ist sie unsichtbar.

## Datenverbrauch überwachen (ISP-Limits)

Unter **Datenverbrauch** siehst Du pro WAN das Volumen des laufenden Monats.

- Die Werte kommen aus den **Interface-Zählern des Routers** — also aus dem
  Kernel, nicht aus Stichproben. Dadurch geht auch zwischen zwei Messungen
  nichts verloren. Kann eine Leitung keine Zähler liefern, rechnet das Dashboard
  ersatzweise aus der gemessenen Rate hoch.
- Ein Router-Neustart setzt die Zähler zurück; das wird erkannt und **nicht**
  als riesiger Verbrauch verbucht.
- Pro Leitung lassen sich **Monatslimit (GB)** und **Warnschwelle (%)** setzen.
  Beim Überschreiten entsteht ein Ereignis (und, falls eingerichtet, ein Alarm) —
  einmalig pro Monat und Schwelle, nicht bei jeder Messung.
- Der Monat wird in UTC gezählt. Die Verbrauchshistorie bleibt ca. 13 Monate
  erhalten, deutlich länger als die feingranularen Messwerte.
- Zusätzlich rechnet das Dashboard den Verbrauch aufs Monatsende hoch. Der
  kleine Strich im Balken zeigt, wo Du bei gleichbleibendem Tempo landest —
  so siehst Du eine Überschreitung, **bevor** sie eintritt. Die Hochrechnung
  startet erst nach etwa 15 % des Monats, damit ein einzelner großer Download
  am 2. keine Fehlprognose auslöst.

## Alarme einrichten

Unter **Alarme** legst Du fest, worüber Du informiert wirst:

| Kanal | Was Du brauchst |
|---|---|
| **Telegram** | Bot-Token (von `@BotFather`) und Chat-ID |
| **Webhook** | Eine URL — bekommt das Ereignis als JSON per POST |
| **E-Mail** | SMTP-Server, Port, Zugangsdaten, Absender und Empfänger |

Ausgelöst wird bei WAN-Ausfall, Wiederkehr, beeinträchtigter Leitung, Wechsel
des Gesamtzustands (z. B. **offline** — der wichtigste Fall) und bei erreichten
Datenlimits.

Zwei Einstellungen steuern die Menge:

- **Schwere:** „Warnung & Fehler" (Standard) oder „nur Fehler".
- **Wiederholsperre:** Dieselbe Meldung geht höchstens einmal pro Zeitfenster
  raus (Standard 10 Minuten). Das verhindert Nachrichtenfluten bei einer
  flatternden Leitung — **neue** Meldungen (eine zweite Leitung fällt aus, oder
  die Entwarnung) kommen davon unabhängig sofort durch. `0` schaltet die Sperre ab.

Mit **Test senden** prüfst Du jeden aktiven Kanal einzeln; das Ergebnis wird pro
Kanal angezeigt. Die Zugangsdaten werden verschlüsselt auf dem VPS abgelegt
(`alerts.enc`) und nie an den Browser zurückgegeben.

---

## Eigene Firewall hinter dem OMR-Router einrichten

Die meisten Nutzer betreiben den OMR-Router nicht als alleinigen
Heimnetz-Router, sondern hängen ihre eigentliche Firewall (OPNsense,
pfSense, Sophos, Fritzbox …) mit deren **WAN-Port** an einen LAN-Port des
OMR-Routers. Das funktioniert heute schon, braucht aber etwas händische
Konfiguration und führt zu einer (harmlosen) Doppel-NAT-Situation:

```
Internet → VPS (öffentliche IP) → Tunnel → OMR-Router → Firewall → Dein LAN
```

**So richtest Du es ein:**

1. **OMR-DHCP auf dem LAN-Port deaktivieren**, an dem die Firewall hängt —
   sonst vergibt sowohl der OMR-Router als auch die Firewall IP-Adressen,
   das kollidiert. In LuCI: *Network → Interfaces → LAN → DHCP Server →
   „Ignore interface"* aktivieren. (Eine direkte Dashboard-Schaltfläche dafür
   ist geplant, siehe `dashboard/docs/routing-plan.de.md`, Abschnitt 9.3 —
   bis dahin über LuCI.)
2. **Firewall mit einer statischen IP im OMR-LAN-Subnetz konfigurieren**,
   z. B. OMR-Router `192.168.100.1`, Firewall-WAN `192.168.100.2/24`,
   Gateway `192.168.100.1`. Nicht per DHCP beziehen lassen.
3. **Port-Weiterleitung für eingehende Verbindungen zur Firewall einrichten**,
   falls die Firewall selbst von außen erreichbar sein soll (z. B. für ihr
   eigenes WireGuard/IPsec): im Dashboard unter **VPS-Endpunkt → Port-
   Weiterleitungen** eine neue Regel anlegen, Ziel über den Topologie-Picker
   auswählen (die Firewall erscheint dort, sobald sie im LAN aktiv ist) statt
   die IP händisch zu tippen.
4. **DDNS auf der Firewall: „externe IP-Ermittlung" statt „WAN-Schnittstelle"
   wählen.** Deine Firewall zeigt als „WAN-IP" die private OMR-LAN-Adresse
   (`192.168.100.2`) — das ist normal und kein Fehler. Für DDNS auf der
   Firewall den Modus wählen, der die öffentliche IP über einen externen
   Prüfdienst ermittelt (bei den meisten Firewall-Betriebssystemen die
   Standardeinstellung oder leicht umstellbar) — dieser sieht korrekt die
   echte VPS-Public-IP, weil darüber der gesamte gebündelte Traffic das
   Internet erreicht.
5. **VPS-Public-IP zum Abgleich**: im Dashboard unter **VPS-Endpunkt → NAT**
   wird die aktuelle öffentliche IPv4/IPv6 des VPS angezeigt — damit lässt
   sich die DDNS-Auflösung der Firewall jederzeit verifizieren.

**Was damit (noch) nicht geht:** ein echtes, NAT-freies Durchreichen einer
*eigenen* öffentlichen IP an die Firewall-WAN-Schnittstelle (also ohne
Doppel-NAT, wie an einem klassischen Modem) ist eine größere, noch nicht
umgesetzte Erweiterung — Konzept und Aufwand dazu stehen in
`dashboard/docs/routing-plan.de.md`, Abschnitt 9.2 („Stufe 3").

---

## Bekannte Einschränkungen (ehrlich)

- **Nur Demo-Modus end-to-end verifiziert.** Die Live-Pfade (omr-admin,
  Router-ubus, Shorewall, WireGuard) sind korrekt verdrahtet, aber der erste
  Lauf gegen echte Hardware ist der erste echte Integrationstest — begleite ihn
  mit Logs.
- **Ein VPS-Endpunkt.** OMR bündelt alle WANs zu *einem* VPS. Echtes Multi-VPS-
  Failover über Standorte gibt es nicht; ein zweiter WireGuard-Server lässt sich
  als **Exit-VPN** hinter dem primären VPS nachschalten (VPS-Endpunkt → Exit-VPN).
- **LuCI-Menüeintrag** „OMR Dashboard" auf dem Router ist eine Image-Änderung im
  Repo `openmptcprouter` und nicht Teil dieses Sidecars. Für den Zugriff genügt
  `BIND_ADDR:3000` bzw. der SSH-Tunnel.
- **Zugangsdaten (`ROUTER_PASS`, `OMR_ADMIN_KEY`, `JWT_SECRET`, …) sind aktuell
  nur über `.env` + Container-Neustart änderbar** — es gibt noch keine
  Settings-Seite im Dashboard dafür (geplant, siehe
  `dashboard/docs/routing-plan.de.md`, Abschnitt 8/10). Bis dahin: Werte in
  `.env` anpassen und `docker compose up -d` ausführen, wie in
  [Schritt 9 der Kurzanleitung](#komplettanleitung-in-12-schritten-kurzfassung)
  beschrieben.
- **Echtes IP-Passthrough an eine eigene Firewall** (ohne Doppel-NAT) ist noch
  nicht umgesetzt — siehe
  [Eigene Firewall hinter dem OMR-Router einrichten](#eigene-firewall-hinter-dem-omr-router-einrichten).
