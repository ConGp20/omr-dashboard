"""Synthetic data source used when ``OMR_DASHBOARD_DEMO`` is enabled.

Produces believable, gently fluctuating status so the whole dashboard — gauges,
link cards, topology, history graphs — can be built and demonstrated without a
real VPS/router pair behind it.
"""
from __future__ import annotations

import math
import random
import time

from schemas import (
    BondState,
    DashboardStatus,
    LinkState,
    LinkStatus,
    LinkType,
    TunnelStatus,
)

_START = time.time()

# Configured demo links. Capacities are in bits/s.
_LINKS = [
    {"id": "wan", "label": "Fiber DSL", "type": LinkType.fiber, "device": "eth0.2",
     "cap_rx": 95e6, "cap_tx": 40e6, "base_lat": 8.0},
    {"id": "wan2", "label": "LTE Telekom", "type": LinkType.lte, "device": "wwan0",
     "cap_rx": 45e6, "cap_tx": 20e6, "base_lat": 24.0},
    {"id": "wan3", "label": "5G Vodafone", "type": LinkType.fiveg, "device": "wwan1",
     "cap_rx": 60e6, "cap_tx": 25e6, "base_lat": 18.0},
]

# Mutable per-link admin state (toggled via the API in demo mode).
_state: dict[str, dict] = {
    l["id"]: {"enabled": True, "priority": i, "label": l["label"], "type": l["type"]}
    for i, l in enumerate(_LINKS)
}


def _wave(period: float, phase: float = 0.0) -> float:
    """0..1 smooth oscillation."""
    t = time.time() - _START
    return (math.sin(2 * math.pi * (t / period) + phase) + 1) / 2


def link_status() -> list[LinkStatus]:
    out: list[LinkStatus] = []
    for idx, link in enumerate(_LINKS):
        st = _state[link["id"]]
        if not st["enabled"]:
            out.append(
                LinkStatus(
                    id=link["id"],
                    label=st["label"],
                    type=st["type"],
                    state=LinkState.disabled,
                    enabled=False,
                    priority=st["priority"],
                    device=link["device"],
                )
            )
            continue

        load = 0.35 + 0.6 * _wave(20 + idx * 7, phase=idx)
        jitter = random.uniform(-0.05, 0.05)
        rx = max(0.0, link["cap_rx"] * (load + jitter))
        tx = max(0.0, link["cap_tx"] * (load + jitter) * 0.7)
        latency = link["base_lat"] + 6 * _wave(13 + idx * 3) + random.uniform(-1.5, 1.5)
        # Loss in percent (0–5 range); 5G link occasionally spikes higher.
        loss = max(0.0, (5.0 if idx == 2 else 0.8) * _wave(31 + idx))

        state = LinkState.up
        if loss > 1.0 or latency > 100:
            state = LinkState.degraded

        out.append(
            LinkStatus(
                id=link["id"],
                label=st["label"],
                type=st["type"],
                state=state,
                enabled=True,
                priority=st["priority"],
                device=link["device"],
                ip=f"203.0.113.{idx + 5}",
                rx_bps=rx,
                tx_bps=tx,
                latency_ms=round(latency, 1),
                packet_loss_pct=round(loss, 2),
            )
        )
    return out


def dashboard_status() -> DashboardStatus:
    links = link_status()
    active = [l for l in links if l.state in (LinkState.up, LinkState.degraded)]
    total_rx = sum(l.rx_bps for l in active)
    total_tx = sum(l.tx_bps for l in active)

    enabled_links = [l for l in links if l.enabled]
    if not active:
        state = BondState.offline
    elif len(active) < len(enabled_links) or any(l.state == LinkState.degraded for l in active):
        state = BondState.degraded
    else:
        state = BondState.bonded

    tunnel = TunnelStatus(
        protocol="glorytun_tcp",
        up=bool(active),
        encryption="ChaCha20-Poly1305",
        rx_bps=total_rx,
        tx_bps=total_tx,
        local_ip="10.255.255.2",
        remote_ip="10.255.255.1",
    )

    return DashboardStatus(
        configured=True,
        state=state,
        links=links,
        tunnel=tunnel,
        total_rx_bps=total_rx,
        total_tx_bps=total_tx,
        active_links=len(active),
        total_links=len(enabled_links),
        vps_public_ip="198.51.100.7",
        exit_vpn=None,
        timestamp=time.time(),
    )


def device_counters() -> dict[str, tuple[float, float]]:
    """Synthetic cumulative interface byte counters, mirroring ``link_status``.

    Monotonically increasing with elapsed runtime so the usage collector sees
    realistic, ever-growing counters (as a real kernel would report).
    """
    elapsed = max(0.0, time.time() - _START)
    out: dict[str, tuple[float, float]] = {}
    for idx, link in enumerate(_LINKS):
        if not _state[link["id"]]["enabled"]:
            continue
        # ~55% average utilisation, converted from bits/s to bytes.
        rx = link["cap_rx"] * 0.55 * elapsed / 8.0
        tx = link["cap_tx"] * 0.38 * elapsed / 8.0
        out[link["device"]] = (rx + idx * 1e6, tx + idx * 5e5)
    return out


def set_link(link_id: str, *, enabled=None, label=None, priority=None, type=None) -> None:
    if link_id not in _state:
        return
    if enabled is not None:
        _state[link_id]["enabled"] = enabled
    if label is not None:
        _state[link_id]["label"] = label
    if priority is not None:
        _state[link_id]["priority"] = priority
    if type is not None:
        _state[link_id]["type"] = type
