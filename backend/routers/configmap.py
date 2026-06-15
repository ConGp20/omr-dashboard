"""Configuration ownership map — who configures what (router / VPS / sync)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from auth import require_user

router = APIRouter(prefix="/config-map", tags=["config-map"])

# Static description of where each configuration area lives. Surfaced in the UI
# so users understand which settings are on the router, on the VPS, or
# generated on the VPS and auto-synced to the router.
CONFIG_MAP = {
    "router": [
        {"key": "wan_interfaces", "label": "WAN-Schnittstellen", "page": "/links",
         "description": "Physische Leitungen, ihre Namen und Typen."},
        {"key": "mptcp_scheduler", "label": "MPTCP-Scheduler", "page": "/protocols",
         "description": "Wie Pakete über die Leitungen verteilt werden."},
        {"key": "qos", "label": "QoS-Regeln (DSCP)", "page": "/qos",
         "description": "Priorisierung von Verkehr auf dem Router."},
        {"key": "domain_routing", "label": "Domain-Routing", "page": "/qos",
         "description": "Welche Domains über welchen Weg geleitet werden."},
        {"key": "lan_dhcp", "label": "LAN / DHCP", "page": "/system",
         "description": "Lokales Netz und Adressvergabe."},
        {"key": "dns", "label": "DNS-Einstellungen", "page": "/dns",
         "description": "Upstream-Resolver und lokale Einträge."},
        {"key": "wan_priority", "label": "WAN-Prioritäten", "page": "/links",
         "description": "Reihenfolge/Gewichtung der Leitungen."},
    ],
    "vps": [
        {"key": "active_protocol", "label": "Aktives Protokoll", "page": "/protocols",
         "description": "Welcher Tunnel-Typ läuft (Glorytun, Shadowsocks, …)."},
        {"key": "protocol_ports", "label": "Protokoll-Ports", "page": "/protocols",
         "description": "Auf welchen Ports die Tunnel lauschen."},
        {"key": "firewall", "label": "Shorewall-Firewall", "page": "/firewall",
         "description": "Welche Ports von außen erreichbar sind."},
        {"key": "port_forwarding", "label": "Port-Weiterleitungen", "page": "/vps",
         "description": "DNAT-Regeln vom VPS ins LAN."},
        {"key": "exit_vpn", "label": "Exit-VPN", "page": "/vps",
         "description": "Optionaler VPN-Ausgang hinter dem VPS."},
        {"key": "nat", "label": "NAT / Masquerading", "page": "/vps",
         "description": "Adressübersetzung am VPS-Ausgang."},
    ],
    "sync": [
        {"key": "tunnel_keys", "label": "Tunnel-Schlüssel/-Passwörter",
         "description": "Auf dem VPS generiert, automatisch zum Router übertragen."},
        {"key": "vps_address", "label": "VPS-IP / Domain",
         "description": "Vom VPS bekannt, im Router hinterlegt."},
        {"key": "mtu", "label": "MTU-Empfehlungen",
         "description": "Vom Tunnel abgeleitet, am Router gesetzt."},
        {"key": "tunnel_ips", "label": "Tunnel-Subnetz-IPs",
         "description": "Adressen der Tunnel-Endpunkte."},
        {"key": "encryption_keys", "label": "Verschlüsselungs-Keys",
         "description": "Schlüsselmaterial der Protokolle."},
    ],
}


@router.get("")
async def config_map(_: str = Depends(require_user)) -> dict:
    return CONFIG_MAP
