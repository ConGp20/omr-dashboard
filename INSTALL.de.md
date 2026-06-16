# OMR Dashboard — Ausführliche Installationsanleitung

Diese Anleitung führt Dich von Null bis zum laufenden Dashboard. Sie ist in vier
Wege gegliedert — wähle den, der zu Dir passt:

- **[Weg 0 — Demo zuerst ausprobieren](#weg-0--demo-zuerst-ausprobieren)** (kein VPS nötig, 2 Minuten)
- **[Weg 1 — Automatisch über das VPS-Install-Script](#weg-1--automatisch-über-das-vps-install-script)** (empfohlen)
- **[Weg 2 — Manuell mit Docker Compose](#weg-2--manuell-mit-docker-compose)**
- **[Weg 3 — Ohne Docker, direkt mit Python + Node](#weg-3--ohne-docker-direkt-mit-python--node)** (Entwicklung/Debug)

Danach: **[Der Einrichtungs-Wizard Schritt für Schritt](#der-einrichtungs-wizard-schritt-für-schritt)**,
**[Zugriff absichern](#zugriff-absichern-tunnel-statt-öffentlich)**,
**[Fehlersuche](#fehlersuche)** und **[Update / Backup](#update--backup)**.

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
