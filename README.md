# OMR Dashboard

A modern, easy-to-understand control panel for **OpenMPTCProuter** — a
Speedify/SpeedFusion-style experience for the technically excellent OMR stack.

It runs as a Docker sidecar **on the VPS**, next to the existing `omr-admin`
service, and aggregates everything (VPS + router) into one clean UI:

- **Guided setup wizard** — connect the VPS, auto-detect WAN links, pick a
  protocol in plain language, and the dashboard pushes all credentials to the
  router for you. No copying keys by hand.
- **Live dashboard** — BONDED / DEGRADED / OFFLINE at a glance, aggregated
  speed, per-link cards, and an **interactive topology** you can click through.
- **Full operations** — port forwarding (incl. exposing your own firewall's VPN
  through the VPS), exit-VPN, QoS profiles, domain routing, DNS, diagnostics.
- **Config-ownership map** — see exactly which setting lives on the router,
  which on the VPS, and what is auto-synced.
- **Monthly data tracking** — per-WAN volume read from the router's interface
  counters, with a monthly cap, warning threshold, and a month-end projection
  that flags an overrun before it happens.
- **System check** — non-blocking advice: misconfiguration hints (public bind
  address, placeholder session secret, missing caps on metered links), plus
  recommendations with the concrete setting to change and a link straight to it.
  Nothing it reports ever blocks an action.
- **Alerts** — Telegram, webhook or e-mail when a line drops, the bond goes
  offline, or a data cap is reached. Repeat-suppression keeps a flapping link
  from flooding your inbox.
- **Encrypted backup/restore** — bundle the whole config into one file and bring
  it back in ~2 minutes. Perfect for occasional/event-based bonding.

> The underlying OMR technology is unchanged — this is purely a usability layer
> on top of the existing APIs. LuCI remains available.

> 📖 **Ausführliche deutsche Installationsanleitung:** [`INSTALL.de.md`](INSTALL.de.md)
> — Schritt für Schritt vom Demo-Test bis zum Live-Betrieb auf dem VPS, inkl.
> Wizard-Walkthrough, Tunnel-Zugriff und Fehlersuche.

---

## Quick start (demo, no VPS needed)

Try the whole UI with synthetic data:

```bash
cd dashboard
docker compose -f docker-compose.dev.yml up
# open http://localhost:3000
```

Or run the two parts directly:

```bash
# backend
cd backend && python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
OMR_DASHBOARD_DEMO=true uvicorn omr_dashboard_api:app --port 8000

# frontend (in another shell)
cd frontend && npm install
BACKEND_URL=http://127.0.0.1:8000 npm run dev
```

## Production (on an existing OMR VPS)

The dashboard is a **self-contained sidecar**: it installs *next to* a working
OpenMPTCProuter VPS without modifying the OMR installation. Easiest path — run
the bundled installer on the VPS:

```bash
git clone https://github.com/ConGp20/omr-dashboard.git /opt/omr-dashboard
cd /opt/omr-dashboard
./install.sh --bind 10.255.247.1      # bind to your WireGuard tunnel IP
```

`install.sh` auto-detects the `omr-admin` server key from the existing
`omr-admin-config.json`, writes `.env`, installs Docker if needed, and starts
the stack. Run `./install.sh --help` for all flags (`--router-pass`, `--demo`,
`--no-start`, …). Nothing in the OMR install is changed.

Or do it by hand:

```bash
cp .env.example .env       # set OMR_ADMIN_KEY, ROUTER_PASS, BIND_ADDR, JWT_SECRET
docker compose up -d --build
```

Then reach it **through the router** at `http://<BIND_ADDR>:3000` (see Security).

For a **fresh** VPS, the OMR VPS install script can also pull the dashboard in
with `DASHBOARD=yes` — it git-clones this repo, writes `.env` from the generated
config, and starts the stack.

---

## Architecture

```
Browser ──/api proxy──▶ Frontend (Next.js, :3000) ──▶ Backend sidecar (FastAPI, :65501)
                                                          ├─▶ omr-admin API   (127.0.0.1:65500)
                                                          ├─▶ Router LuCI ubus (http://ROUTER_IP/ubus)
                                                          └─▶ Shorewall / WireGuard (local)
```

- **Frontend** (`frontend/`) — Next.js 14 App Router, Tailwind, ReactFlow
  (topology), Recharts (history). The browser only ever talks to the Next.js
  server, which proxies to the backend server-side — so the backend stays off
  the public network and the admin key never reaches the browser.
- **Backend** (`backend/`) — FastAPI. Aggregates live status, runs a 10s poller
  (in sync with `omr-service`) into a SQLite store, exposes an SSE stream, and
  wraps the existing APIs. Additive on port 65501, so it survives `omr-admin`
  upgrades. Set `OMR_DASHBOARD_DEMO=true` for synthetic data.

## Security: reach it through the router, not the public net

The dashboard is meant to be reached over the **WireGuard management tunnel**
that OMR already sets up, not exposed publicly:

1. Set `BIND_ADDR` in `.env` to your tunnel IP (e.g. `10.255.247.1`).
2. The VPS firewall (Shorewall) does **not** open ports 3000/65501 to the net.
3. The router gets an "OMR Dashboard" link pointing at `http://10.255.247.1:3000`
   — reachable because your browser is behind the router, inside the tunnel net.

For first-time setup (before the tunnel exists), keep `BIND_ADDR=127.0.0.1` and
reach it via an SSH tunnel: `ssh -L 3000:127.0.0.1:3000 root@<vps>`.

---

## Tests

```bash
cd backend && . .venv/bin/activate
pytest                      # 110 tests, all green in demo mode

cd ../frontend && npm run build    # type-checks + builds all routes
```

## Multi-server note (vs. Speedify)

OpenMPTCProuter bonds all WAN links to **one** VPS endpoint. Native multi-VPS
failover across locations is not supported. You can chain a second WireGuard
server as an **exit-VPN** behind the primary VPS (configurable under
*VPS-Endpunkt → Exit-VPN*), but that is an exit path, not parallel endpoints.
