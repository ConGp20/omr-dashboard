"""Pydantic schemas shared across the OMR Dashboard backend.

These models are the single source of truth for the API contract. The frontend
TypeScript types in ``frontend/src/lib/types.ts`` mirror them.
"""
from __future__ import annotations

import ipaddress
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


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
    device: Optional[str] = None   # L3 device name, used to read byte counters
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
def _validate_ip(v: str) -> str:
    """Reject anything that is not a plain IP — the value is written verbatim
    into the Shorewall DNAT rule, so it must never carry extra tokens."""
    v = v.strip()
    try:
        ipaddress.ip_address(v)
    except ValueError as exc:
        raise ValueError("muss eine gültige IP-Adresse sein") from exc
    return v


def _validate_cidr(v: str) -> str:
    v = v.strip()
    try:
        ipaddress.ip_network(v, strict=False)
    except ValueError as exc:
        raise ValueError(f"{v!r} ist kein gültiges CIDR (z. B. 203.0.113.0/24)") from exc
    return v


class IngressTarget(BaseModel):
    """Extra weighted destination for load-balanced port forwarding (R2)."""
    dest_ip: str
    dest_port: int = Field(ge=1, le=65535)
    weight: int = Field(default=1, ge=1, le=10)

    @field_validator("dest_ip")
    @classmethod
    def _validate_dest_ip(cls, v: str) -> str:
        return _validate_ip(v)


class PortForward(BaseModel):
    id: Optional[str] = None
    description: str = ""
    proto: Literal["tcp", "udp", "tcp/udp"] = "tcp"
    src_port: int = Field(ge=1, le=65535)
    src_port_end: Optional[int] = Field(
        default=None, ge=1, le=65535,
        description="Wenn gesetzt, wird ein Portbereich src_port..src_port_end weitergeleitet.",
    )
    dest_ip: str
    dest_port: int = Field(ge=1, le=65535)
    enabled: bool = True
    extra_targets: list[IngressTarget] = Field(
        default_factory=list,
        description="Weitere Ziele für gewichtete Lastverteilung (Round-Robin nach Gewicht).",
    )
    allow_src_cidrs: list[str] = Field(
        default_factory=list,
        description="Wenn gesetzt, ist die Weiterleitung nur von diesen Quell-Netzen aus erreichbar.",
    )
    deny_src_cidrs: list[str] = Field(
        default_factory=list,
        description="Diese Quell-Netze werden explizit blockiert, bevor die Weiterleitung greift.",
    )
    rate_limit_per_min: Optional[int] = Field(default=None, ge=1, le=100000)

    @field_validator("dest_ip")
    @classmethod
    def _validate_dest_ip(cls, v: str) -> str:
        return _validate_ip(v)

    @field_validator("description")
    @classmethod
    def _clean_description(cls, v: str) -> str:
        """Collapse all whitespace so the description can't break out of the
        single-line shorewall rule/comment it is rendered into."""
        return " ".join(v.split())

    @field_validator("allow_src_cidrs", "deny_src_cidrs")
    @classmethod
    def _validate_cidrs(cls, v: list[str]) -> list[str]:
        return [_validate_cidr(c) for c in v]

    @model_validator(mode="after")
    def _validate_port_range(self) -> "PortForward":
        if self.src_port_end is not None and self.src_port_end < self.src_port:
            raise ValueError("src_port_end muss größer oder gleich src_port sein")
        return self


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
_FIREWALL_ZONES = {"net", "fw", "vpn", "lan", "loc", "all"}


def _validate_port_expr(v: str) -> str:
    """Validate a port expression (``80``, ``80,443``, ``5000:5010``, mixes).

    The value is written verbatim into the Shorewall rules file, so anything
    beyond digits, commas and range colons must be rejected — whitespace or
    stray tokens would become extra columns in the generated rule.
    """
    v = v.strip()
    if not v:
        raise ValueError("Port darf nicht leer sein")
    for part in v.split(","):
        lo, sep, hi = part.partition(":")
        bounds = (lo, hi) if sep else (lo,)
        for b in bounds:
            if not b.isdigit() or not (1 <= int(b) <= 65535):
                raise ValueError(f"{part!r} ist kein gültiger Port oder Bereich")
        if sep and int(lo) >= int(hi):
            raise ValueError(f"Bereich {part!r} muss aufsteigend sein")
    return v


class FirewallRule(BaseModel):
    id: Optional[str] = None
    action: Literal["allow", "block"] = "allow"
    src_zone: str = "net"
    dest_zone: str = "fw"
    proto: Literal["tcp", "udp", "tcp/udp"] = "tcp"
    port: str = ""
    description: str = ""
    enabled: bool = True

    @field_validator("port")
    @classmethod
    def _validate_port(cls, v: str) -> str:
        return _validate_port_expr(v)

    @field_validator("src_zone", "dest_zone")
    @classmethod
    def _validate_zone(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in _FIREWALL_ZONES:
            raise ValueError(f"unbekannte Zone {v!r}")
        return v

    @field_validator("description")
    @classmethod
    def _clean_description(cls, v: str) -> str:
        # Same rationale as PortForward: the description is rendered into a
        # single-line comment in the rules file.
        return " ".join(v.split())


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
# Monthly data usage (per WAN), for tracking ISP volume limits
# --------------------------------------------------------------------------- #
class LinkUsage(BaseModel):
    link_id: str
    label: str = ""
    rx_bytes: float = 0.0
    tx_bytes: float = 0.0
    total_bytes: float = 0.0
    cap_gb: Optional[float] = None      # monthly cap in GB; None = no limit set
    warn_pct: int = 80                  # warn threshold, percent of the cap
    used_pct: Optional[float] = None    # total vs cap; None when no cap is set
    over_warn: bool = False
    over_cap: bool = False
    # Linear projection to month end from the rate so far — lets the UI warn
    # before a cap is actually hit rather than after.
    projected_bytes: float = 0.0
    projected_pct: Optional[float] = None
    projected_over_cap: bool = False


class UsageResponse(BaseModel):
    month: str                          # "YYYY-MM" (UTC)
    total_bytes: float = 0.0
    links: list[LinkUsage] = Field(default_factory=list)
    day_of_month: int = 1
    days_in_month: int = 30


class QuotaUpdate(BaseModel):
    cap_gb: Optional[float] = Field(default=None, ge=0)   # 0/None clears the cap
    warn_pct: Optional[int] = Field(default=None, ge=1, le=100)


# --------------------------------------------------------------------------- #
# Alerts / notifications
# --------------------------------------------------------------------------- #
class AlertConfigUpdate(BaseModel):
    """Partial update of the alert channel configuration.

    All fields optional: only provided values are applied. Empty strings on
    secret fields are ignored so a save that doesn't re-enter the secret keeps
    the stored one.
    """
    min_severity: Optional[Literal["warn", "error"]] = None
    # 0 disables throttling; otherwise the same event is sent at most once per
    # this many minutes (flapping protection).
    cooldown_minutes: Optional[int] = Field(default=None, ge=0, le=1440)
    telegram_enabled: Optional[bool] = None
    telegram_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    webhook_enabled: Optional[bool] = None
    webhook_url: Optional[str] = None
    email_enabled: Optional[bool] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = Field(default=None, ge=1, le=65535)
    smtp_user: Optional[str] = None
    smtp_pass: Optional[str] = None
    smtp_tls: Optional[bool] = None
    email_from: Optional[str] = None
    email_to: Optional[str] = None


class AlertConfigPublic(BaseModel):
    """Alert config as returned to the UI — secrets masked to booleans."""
    min_severity: str = "warn"
    cooldown_minutes: int = 10
    telegram_enabled: bool = False
    telegram_chat_id: Optional[str] = None
    telegram_token_set: bool = False
    webhook_enabled: bool = False
    webhook_url: Optional[str] = None
    email_enabled: bool = False
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_pass_set: bool = False
    smtp_tls: bool = True
    email_from: Optional[str] = None
    email_to: Optional[str] = None


class AlertTestResult(BaseModel):
    results: dict[str, str] = Field(default_factory=dict)  # channel -> outcome


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
# Settings (post-setup editable connection & security credentials)
# --------------------------------------------------------------------------- #
class ConnectionSettings(BaseModel):
    router_ip: str
    router_user: str
    router_pass_set: bool = False
    omr_admin_key_set: bool = False
    overridden: list[str] = Field(default_factory=list)


class ConnectionSettingsUpdate(BaseModel):
    router_ip: Optional[str] = None
    router_user: Optional[str] = None
    router_pass: Optional[str] = None
    omr_admin_key: Optional[str] = None


class ConnectionTestResult(BaseModel):
    router_reachable: bool = False
    router_detail: str = ""
    omr_admin_reachable: bool = False
    omr_admin_detail: str = ""


class SecuritySettings(BaseModel):
    dashboard_user: str
    dashboard_pass_set: bool = False
    jwt_secret_set: bool = False
    overridden: list[str] = Field(default_factory=list)


class SecuritySettingsUpdate(BaseModel):
    dashboard_user: Optional[str] = None
    dashboard_pass: Optional[str] = None
    jwt_secret: Optional[str] = None


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


class AuthStatus(BaseModel):
    auth_required: bool
    demo: bool = False
    username: str = "admin"


# --------------------------------------------------------------------------- #
# Configuration advisor (non-blocking hints and recommendations)
# --------------------------------------------------------------------------- #
class Finding(BaseModel):
    id: str
    severity: Literal["error", "warn", "info"]
    title: str
    detail: str                        # what is wrong and why it matters
    action: str                        # what to do about it
    page: Optional[str] = None         # deep link to where it is changed
    category: str = "general"


class HealthReport(BaseModel):
    findings: list[Finding] = Field(default_factory=list)
    errors: int = 0
    warnings: int = 0
    infos: int = 0
    checked: int = 0
