# Erster Test auf der echten VPS — Ablauf & Beweissicherung

Dieser Leitfaden führt durch den ersten Integrationstest gegen echte Hardware.
Er ist so aufgebaut, dass bei jedem Schritt klar ist, **was Erfolg ist** und
**welche Logs bei einem Fehler helfen**. Reihenfolge einhalten — jeder Schritt
baut auf dem vorherigen auf.

> Getestet ohne Hardware sind bereits: alle 155 Backend-Tests, die komplette
> UI im Browser (15 Seiten + Login-Flow), install.sh, die Shorewall-Datei-
> verwaltung. Dieser Test prüft erstmals: echte omr-admin-Aufrufe, Router-ubus
> (Wizard, Zähler), shorewall-Reload, Alarm-Versand.

## 0) Voraussetzungen

- VPS mit laufendem OpenMPTCProuter (omr-admin aktiv auf Port 65500)
- Router verbunden (WireGuard-Management-Tunnel steht)
- SSH-Zugang zur VPS als root

## 1) Installation (5 Min)

```bash
git clone https://github.com/ConGp20/omr-dashboard.git /opt/omr-dashboard
cd /opt/omr-dashboard
./install.sh                        # bindet an 127.0.0.1 — sicher für den Test
```

**Erfolg:** `Wrote .env` + `Up. Reachable at http://127.0.0.1:3000`.
**Bei Fehler:** Ausgabe von `docker compose logs backend frontend` sichern.

Falls der Schlüssel nicht erkannt wird („could not auto-detect"): prüfen, ob
`/etc/openmptcprouter-vps-admin/omr-admin-config.json` existiert und `jq`
installiert ist; sonst `./install.sh --admin-key '<Server-Key>'`.

## 2) Zugriff per SSH-Tunnel

Auf dem eigenen Rechner:

```bash
ssh -L 3000:127.0.0.1:3000 root@<vps-ip>
# Browser: http://localhost:3000
```

**Erfolg:** Login-Maske erscheint; Anmeldung mit Benutzer `admin` und dem
`DASHBOARD_PASS` aus `/opt/omr-dashboard/.env`.

## 3) Systemcheck zuerst (1 Min)

Im Dashboard: **Systemcheck** öffnen.

**Erfolg:** Seite lädt, Befunde erscheinen (z. B. fehlende Datenlimits).
Ein roter Befund „Keine Verbindung" hier bedeutet: Backend erreicht omr-admin
nicht → Schritt 4 klärt das.

## 4) VPS-Strecke: Status & omr-admin (2 Min)

Übersicht öffnen. **Erfolg:** Status zeigt BONDED/DEGRADED (nicht dauerhaft
OFFLINE), Leitungen erscheinen mit echten Namen.

**Bei OFFLINE/leer:**
```bash
docker compose logs backend --tail 100 > /tmp/omr-dash-backend.log
curl -sk https://127.0.0.1:65500/ -H "Authorization: Bearer $(grep OMR_ADMIN_KEY /opt/omr-dashboard/.env | cut -d= -f2)"
```
Beide Ausgaben sichern — sie zeigen, ob omr-admin antwortet und was das
Backend daraus macht.

## 5) Router-Strecke: Verbindungstest (2 Min)

**System → Verbindung**: Router-Passwort eintragen → **Verbindung testen**.

**Erfolg:** „Router erreichbar" ✓. Danach unter **Verbindungen** prüfen, ob
die WANs mit Live-Werten (Mbps/Latenz) erscheinen.

## 6) Firewall-Regel end-to-end (3 Min) — erster Schreibtest

**Firewall & Ports** → Vorlage „Web-Server" → **Öffnen**.

```bash
grep -A5 "OMR-DASHBOARD RULES" /etc/shorewall/rules   # Regel in der Datei?
iptables -L -n | grep -E "dpt:(80|443)" | head        # Regel aktiv?
```

**Erfolg:** Beides ja. Danach Regel im Dashboard wieder **entfernen** und
beide Kommandos erneut — Regel muss verschwinden.
**Wenn die Datei stimmt, aber iptables nicht:** `docker compose logs backend | grep -i shorewall`
— die Meldung dort sagt, warum der Reload scheiterte.

## 7) Datenverbrauch (nach ~10 Min Laufzeit)

**Datenverbrauch** öffnen. **Erfolg:** Zahlen wachsen (echte Router-Zähler).
Bleibt alles auf 0: `docker compose logs backend | grep -i "usage\|device"` sichern.

## 8) Alarm-Versand (2 Min)

**Alarme** → Telegram-Bot-Token + Chat-ID eintragen → Speichern → **Test senden**.
**Erfolg:** Nachricht kommt an; Ergebnis pro Kanal wird angezeigt.

## 9) Wizard NUR auf Testsystemen

Der Wizard **überschreibt Router-Konfiguration** (VPS-Eintrag, Schlüssel,
forceretrieve). Auf einem produktiv genutzten Router: auslassen oder erst
Backup ziehen (**System → Backup** + Router-Backup in LuCI).

**Erfolg:** Alle Schritte grün, Tunnel kommt nach dem Apply wieder hoch.

## 10) Danach: Tunnel-Zugriff statt SSH

`.env`: `BIND_ADDR=<WireGuard-Tunnel-IP>` (z. B. 10.255.247.1), dann
`docker compose up -d`. Dashboard ist ab jetzt nur noch durch den Tunnel
erreichbar.

---

## Wenn etwas schiefgeht

Bitte diese drei Dinge sichern und melden — damit ist jede Diagnose möglich:

```bash
docker compose logs backend --tail 200 > /tmp/omr-dash-backend.log
docker compose logs frontend --tail 50 > /tmp/omr-dash-frontend.log
docker compose ps >> /tmp/omr-dash-backend.log
```

plus die genaue Aktion im Dashboard (Seite + Klick) und was stattdessen
passiert ist. Kein Schritt dieses Tests kann die OMR-Installation selbst
beschädigen — Ausnahme ist der Wizard (Schritt 9).
