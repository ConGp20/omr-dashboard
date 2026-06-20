#!/bin/sh
# OMR Dashboard — standalone installer for an EXISTING OpenMPTCProuter VPS.
#
# This is the purely-additive install path: run it on a VPS that already has a
# working OpenMPTCProuter (omr-admin) setup and it installs the dashboard as a
# Docker sidecar next to it — without touching the OMR installation itself.
#
# It auto-detects the omr-admin credentials from the existing config so you
# normally don't have to type anything. Everything is overridable via flags or
# environment variables.
#
# Usage:
#   ./install.sh                         # auto-detect, bind to 127.0.0.1
#   ./install.sh --bind 10.255.247.1     # expose through the WireGuard tunnel
#   ./install.sh --router-pass 'secret'  # also let the dashboard reach the router
#   OMR_ADMIN_KEY=... ./install.sh       # override auto-detection
#
# Flags:
#   --bind ADDR          BIND_ADDR for the dashboard (default: 127.0.0.1)
#   --router-ip IP       Router LuCI IP (default: 192.168.100.1)
#   --router-user USER   Router user (default: root)
#   --router-pass PASS   Router password (default: empty — set later in the UI)
#   --admin-key KEY      omr-admin server key (default: auto-detected)
#   --dashboard-pass P   Dashboard login password (default: omr-admin admin pass)
#   --demo               Install in demo mode (synthetic data, no live VPS)
#   --no-start           Write .env but do not run docker compose
#   --force              Overwrite an existing .env
#   -h, --help           Show this help
set -eu

OMR_ADMIN_CONFIG="${OMR_ADMIN_CONFIG:-/etc/openmptcprouter-vps-admin/omr-admin-config.json}"

BIND_ADDR="${BIND_ADDR:-127.0.0.1}"
ROUTER_IP="${ROUTER_IP:-192.168.100.1}"
ROUTER_USER="${ROUTER_USER:-root}"
ROUTER_PASS="${ROUTER_PASS:-}"
OMR_ADMIN_KEY="${OMR_ADMIN_KEY:-}"
DASHBOARD_PASS="${DASHBOARD_PASS:-}"
DEMO="${OMR_DASHBOARD_DEMO:-false}"
DO_START=yes
FORCE=no

while [ $# -gt 0 ]; do
	case "$1" in
		--bind) BIND_ADDR="$2"; shift 2 ;;
		--router-ip) ROUTER_IP="$2"; shift 2 ;;
		--router-user) ROUTER_USER="$2"; shift 2 ;;
		--router-pass) ROUTER_PASS="$2"; shift 2 ;;
		--admin-key) OMR_ADMIN_KEY="$2"; shift 2 ;;
		--dashboard-pass) DASHBOARD_PASS="$2"; shift 2 ;;
		--demo) DEMO=true; shift ;;
		--no-start) DO_START=no; shift ;;
		--force) FORCE=yes; shift ;;
		-h|--help) sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
		*) echo "Unknown option: $1" >&2; exit 2 ;;
	esac
done

# Operate from the repo directory (where docker-compose.yml lives).
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

log() { printf '%s\n' "OMR Dashboard: $*"; }

# --- Auto-detect omr-admin credentials from the existing install -------------
read_admin_field() {
	# $1 = jq path expression
	[ -f "$OMR_ADMIN_CONFIG" ] || return 1
	if command -v jq >/dev/null 2>&1; then
		jq -r "$1 // empty" "$OMR_ADMIN_CONFIG" 2>/dev/null | tr -d '\n'
	fi
}

if [ "$DEMO" != "true" ]; then
	if [ -z "$OMR_ADMIN_KEY" ]; then
		OMR_ADMIN_KEY="$(read_admin_field '.users[0].openmptcprouter.user_password' || true)"
		[ -n "$OMR_ADMIN_KEY" ] && log "Detected omr-admin server key from $OMR_ADMIN_CONFIG"
	fi
	if [ -z "$DASHBOARD_PASS" ]; then
		DASHBOARD_PASS="$(read_admin_field '.users[0].admin.user_password' || true)"
	fi
	if [ -z "$OMR_ADMIN_KEY" ]; then
		log "WARNING: could not auto-detect the omr-admin key."
		log "         Pass it with --admin-key or OMR_ADMIN_KEY=, or use --demo to try the UI."
	fi
fi

# --- Docker ------------------------------------------------------------------
if [ "$DO_START" = "yes" ] && ! command -v docker >/dev/null 2>&1; then
	log "Installing Docker..."
	wget -qO /tmp/get-docker.sh https://get.docker.com
	sh /tmp/get-docker.sh >/dev/null 2>&1
	rm -f /tmp/get-docker.sh
fi

# --- .env --------------------------------------------------------------------
if [ -f .env ] && [ "$FORCE" != "yes" ]; then
	log ".env already exists — keeping it (use --force to overwrite)."
else
	JWT_SECRET="$(od -vN 32 -An -tx1 /dev/urandom | tr -d ' \n')"
	cat > .env <<EOF
OMR_DASHBOARD_DEMO=${DEMO}
OMR_ADMIN_KEY=${OMR_ADMIN_KEY}
ROUTER_IP=${ROUTER_IP}
ROUTER_USER=${ROUTER_USER}
ROUTER_PASS=${ROUTER_PASS}
BIND_ADDR=${BIND_ADDR}
DASHBOARD_PASS=${DASHBOARD_PASS}
JWT_SECRET=${JWT_SECRET}
EOF
	chmod 600 .env
	log "Wrote .env (bind ${BIND_ADDR}, demo=${DEMO})."
fi

# --- Start -------------------------------------------------------------------
if [ "$DO_START" = "yes" ]; then
	log "Starting the dashboard stack..."
	if docker compose up -d --build; then
		log "Up. Reachable at http://${BIND_ADDR}:3000 (through the router tunnel)."
		[ "$BIND_ADDR" = "127.0.0.1" ] && \
			log "Tip: from your machine run  ssh -L 3000:127.0.0.1:3000 root@<vps>  then open http://localhost:3000"
	else
		log "docker compose failed — fix the error above and re-run, or start manually."
		exit 1
	fi
else
	log "Skipped start (--no-start). Run 'docker compose up -d --build' when ready."
fi
