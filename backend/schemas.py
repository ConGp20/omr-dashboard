"""Pydantic schemas shared across the OMR Dashboard backend.

These models are the single source of truth for the API contract. The frontend
TypeScript types in ``frontend/src/lib/types.ts`` mirror them.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #
class BondState(str, Enum):
    bonded = "bonded"          # all configured links up
    degraded = "degraded"      # at least one link up, at least one down/poor
    offline = "offline"        # tunnel down / no links


class LinkState(str, Enum):
    up = "up"
    degraded = "degraded"      # high latency or packet loss
    down = "down"
    disabled = "disabled"      # administratively disabled


class LinkType(str, Enum):
    fiber = "fiber"
    dsl = "dsl"
    lte = "lte"
    fiveg = "5g"
    ethernet = "ethernet"
    satellite = "satellite"
    other = "other"


class ConfigOwner(str, Enum):
    router = "router"          # configured on and lives on the router
    vps = "vps"                # configured on and lives on the VPS
    sync = "sync"              # generated on VPS, auto-pushed to router


# --------------------------------------------------------------------------- #
# Links
# --------------------------------------------------------------------------- #
class LinkStatus(BaseModel):
    id: str
    label: str
    type: LinkType = LinkType.other
    state: LinkState = LinkState.down
    enabled: bool = True
    priority: int = 0
    ip: Optional[str] = None
    rx_bps: float = 0.0
    tx_bps: float = 0.0
    latency_ms: Optional[float] = None
    packet_loss_pct: Optional[float] = None
    multipath: Literal["on", "off", "backup", "handover", "signal"] = "on"


class LinkUpdate(BaseModel):
    label: Optional[str] = None
    type: Optional[LinkType] = None
    enabled: Optional[bool] = None
    priority: Optional[int] = None
    multipath: Optional[str] = None


# --------------------------------------------------------------------------- #
# Aggregated status / topology
# --------------------------------------------------------------------------- #
class TunnelStatus(BaseModel):
    protocol: str
    up: bool
    encryption: Optional[str] = None
    rx_bps: float = 0.0
    tx_bps: float = 0.0
    local_ip: Optional[str] = None
    remote_ip: Optional[str] = None


class DashboardStatus(BaseModel):
    configured: bool = True
    state: BondState = BondState.offline
    links: list[LinkStatus] = Field(default_factory=list)
    tunnel: Optional[TunnelStatus] = None
    total_rx_bps: float = 0.0
    total_tx_bps: float = 0.0
    active_links: int = 0
    total_links: int = 0
    vps_public_ip: Optional[str] = None
    exit_vpn: Optional[str] = None     # name of exit VPN if traffic leaves via one
    timestamp: float = 0.0


class TopoNode(BaseModel):
    id: str
    type: str                  # "wan" | "router" | "tunnel" | "vps" | "internet" | "exit" | "portforward"
    label: str
    state: str = "up"          # up | degraded | down
    owner: Optional[ConfigOwner] = None
    detail: dict[str, Any] = Field(default_factory=dict)


class TopoEdge(BaseModel):
    id: str
    source: str
    target: str
    animated: bool = False
    label: Optional[str] = None
    bps: float = 0.0


class Topology(BaseModel):
    nodes: list[TopoNode] = Field(default_factory=list)
    edges: list[TopoEdge] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Protocols
# --------------------------------------------------------------------------- #
class ProtocolInfo(BaseModel):
    id: str                    # glorytun_tcp, shadowsocks, wireguard, mlvpn, ...
    name: str
    active: bool = False
    available: bool = True
    good_for: str = ""
    avoid_when: str = ""
    technical: str = ""
    vps_port: Optional[int] = None
    recommended: bool = False


class ProtocolSwitch(BaseModel):
    protocol: str


class SchedulerUpdate(BaseModel):
    scheduler: str             # default, roundrobin, redundant, blest, ...


class ProtocolTuning(BaseModel):
    mtu: Optional[int] = None
    congestion: Optional[str] = None
    tcp_fast_open: Optional[bool] = None


# --------------------------------------------------------------------------- #
# VPS endpoint management
# --------------------------------------------------------------------------- #
class PortForward(BaseModel):
    id: Optional[str] = None
    description: str = ""
    proto: Literal["tcp", "udp", "tcp/udp"] = "tcp"
    src_port: int
    dest_ip: str
    dest_port: int
    enabled: bool = True


class ExitVpn(BaseModel):
    enabled: bool = False
    type: Literal["wireguard", "openvpn", "none"] = "none"
    endpoint: Optional[str] = None
    public_key: Optional[str] = None
    private_key: Optional[str] = None
    allowed_ips: str = "0.0.0.0/0"
    kill_switch: bool = False


class NatStatus(BaseModel):
    masquerade: bool = True
    public_ipv4: Optional[str] = None
    public_ipv6: Optional[str] = None
    tunnel_clients: list[str] = Field(default_factory=list)


class TopologyHost(BaseModel):
    """A host reachable behind the router, used by the port-forward picker."""
    ip: str
    label: str = ""
    source: str = "lan"        # router | lan | mdns


# --------------------------------------------------------------------------- #
# Firewall
# --------------------------------------------------------------------------- #
class FirewallRule(BaseModel):
    id: Optional[str] = None
    action: Literal["allow", "block"] = "allow"
    src_zone: str = "net"
    dest_zone: str = "fw"
    proto: Literal["tcp", "udp", "tcp/udp"] = "tcp"
    port: str = ""
    description: str = ""
    enabled: bool = True


# --------------------------------------------------------------------------- #
# QoS
# --------------------------------------------------------------------------- #
class QosProfile(BaseModel):
    active: str = "default"    # gaming | streaming | work | download | default
    available: list[str] = Field(default_factory=list)


class DomainRule(BaseModel):
    id: Optional[str] = None
    domain: str
    target: str = "vpn"        # vpn | wanX | block


# --------------------------------------------------------------------------- #
# DNS
# --------------------------------------------------------------------------- #
class DnsConfig(BaseModel):
    upstream: list[str] = Field(default_factory=list)
    mode: Literal["classic", "doh", "dot"] = "classic"
    local_entries: list[dict[str, str]] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Metrics & events
# --------------------------------------------------------------------------- #
class MetricPoint(BaseModel):
    ts: int
    link_id: str
    rx_bps: float
    tx_bps: float
    latency_ms: Optional[float] = None
    packet_loss_pct: Optional[float] = None


class MetricsResponse(BaseModel):
    period: str
    points: list[MetricPoint] = Field(default_factory=list)


class Event(BaseModel):
    ts: int
    type: str
    detail: str
    severity: Literal["info", "warn", "error"] = "info"


# --------------------------------------------------------------------------- #
# Diagnostics
# --------------------------------------------------------------------------- #
class PingRequest(BaseModel):
    target: str
    count: int = 5


class PingResult(BaseModel):
    source: str                # "router" | "vps"
    target: str
    min_ms: Optional[float] = None
    avg_ms: Optional[float] = None
    max_ms: Optional[float] = None
    loss_pct: Optional[float] = None
    raw: str = ""


# --------------------------------------------------------------------------- #
# System / versions / backup
# --------------------------------------------------------------------------- #
class ComponentVersion(BaseModel):
    component: str
    installed: str
    available: Optional[str] = None
    update_available: bool = False
    changelog_url: Optional[str] = None


class VersionsResponse(BaseModel):
    components: list[ComponentVersion] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Wizard
# --------------------------------------------------------------------------- #
class WizardConnect(BaseModel):
    vps_ip: str
    omr_key: str


class WizardConnectResult(BaseModel):
    success: bool
    vps_version: Optional[str] = None
    current_vpn: Optional[str] = None
    protocols_available: list[str] = Field(default_factory=list)
    error: Optional[str] = None


class WizardDetectWans(BaseModel):
    router_ip: str
    router_user: str = "root"
    router_pass: str = ""


class WizardWan(BaseModel):
    id: str
    interface: str
    detected_type: LinkType = LinkType.other
    label: str = ""
    ip: Optional[str] = None
    up: bool = False
    enabled: bool = True


class WizardDetectResult(BaseModel):
    wans: list[WizardWan] = Field(default_factory=list)
    error: Optional[str] = None


class WizardApply(BaseModel):
    vps_ip: str
    omr_key: str
    router_ip: str
    router_user: str = "root"
    router_pass: str = ""
    protocol: str
    wans: list[WizardWan] = Field(default_factory=list)
    lan_ip: Optional[str] = None
    dhcp_range: Optional[str] = None


class WizardApplyStep(BaseModel):
    step: str
    ok: bool
    detail: str = ""


class WizardApplyResult(BaseModel):
    success: bool
    steps: list[WizardApplyStep] = Field(default_factory=list)
    download_mbps: Optional[float] = None
    upload_mbps: Optional[float] = None


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
