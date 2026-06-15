"""VPS endpoint management: port forwarding, exit-VPN, routing, NAT."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from auth import require_user
from config import get_settings
from deps import get_aggregator
from schemas import ExitVpn, NatStatus, PortForward, TopologyHost
from services.omr_proxy import OmrProxy
from services.router_proxy import RouterProxy
from services.shorewall_service import ShorewallService
from services.wireguard_service import WireguardService

router = APIRouter(prefix="/vps", tags=["vps"])


# --- port forwarding ------------------------------------------------------ #
@router.get("/portforward", response_model=list[PortForward])
async def list_forwards(_: str = Depends(require_user)) -> list[PortForward]:
    return ShorewallService().list_forwards()


@router.post("/portforward", response_model=PortForward)
async def add_forward(pf: PortForward, _: str = Depends(require_user)) -> PortForward:
    return ShorewallService().add_forward(pf)


@router.put("/portforward/{pf_id}", response_model=PortForward)
async def update_forward(pf_id: str, pf: PortForward, _: str = Depends(require_user)) -> PortForward:
    result = ShorewallService().update_forward(pf_id, pf)
    if result is None:
        raise HTTPException(status_code=404, detail="Weiterleitung nicht gefunden")
    return result


@router.delete("/portforward/{pf_id}")
async def delete_forward(pf_id: str, _: str = Depends(require_user)) -> dict:
    if not ShorewallService().delete_forward(pf_id):
        raise HTTPException(status_code=404, detail="Weiterleitung nicht gefunden")
    return {"success": True}


@router.get("/hosts", response_model=list[TopologyHost])
async def topology_hosts(_: str = Depends(require_user)) -> list[TopologyHost]:
    """Hosts reachable behind the router, for the port-forward target picker."""
    settings = get_settings()
    if settings.demo:
        return [
            TopologyHost(ip="192.168.100.1", label="Router-Peer", source="router"),
            TopologyHost(ip="192.168.100.2", label="Firewall (OPNsense)", source="lan"),
            TopologyHost(ip="192.168.100.10", label="NAS", source="mdns"),
            TopologyHost(ip="192.168.100.20", label="Server", source="lan"),
        ]
    # Real mode: surface the router itself; richer LAN discovery is best-effort.
    hosts = [TopologyHost(ip=settings.router_ip, label="Router-Peer", source="router")]
    return hosts


# --- exit vpn ------------------------------------------------------------- #
@router.get("/exit-vpn", response_model=ExitVpn)
async def get_exit_vpn(_: str = Depends(require_user)) -> ExitVpn:
    return WireguardService().get_exit_vpn()


@router.put("/exit-vpn")
async def set_exit_vpn(config: ExitVpn, _: str = Depends(require_user)) -> dict:
    result, warning = WireguardService().set_exit_vpn(config)
    out = result.model_dump()
    if warning:
        out["warning"] = warning
    return out


# --- nat / routing -------------------------------------------------------- #
@router.get("/nat", response_model=NatStatus)
async def nat_status(_: str = Depends(require_user)) -> NatStatus:
    settings = get_settings()
    status = await get_aggregator().status()
    if settings.demo:
        return NatStatus(
            masquerade=True,
            public_ipv4=status.vps_public_ip or "198.51.100.7",
            public_ipv6="2001:db8::7",
            tunnel_clients=["10.255.255.2", "10.255.247.2"],
        )
    return NatStatus(masquerade=True, public_ipv4=status.vps_public_ip)


@router.get("/routing")
async def routing(_: str = Depends(require_user)) -> dict:
    """Simplified routing overview."""
    settings = get_settings()
    exit_vpn = WireguardService().get_exit_vpn()
    if settings.demo or not exit_vpn.enabled:
        default = "exit-vpn" if exit_vpn.enabled else "direct"
    else:
        default = "exit-vpn" if exit_vpn.enabled else "direct"
    return {
        "default_exit": default,
        "exit_vpn_enabled": exit_vpn.enabled,
        "routes": [
            {"destination": "0.0.0.0/0", "via": "Exit-VPN" if exit_vpn.enabled else "Internet (direkt)"},
            {"destination": "Tunnel-Clients", "via": "Router-Peer"},
        ],
    }
