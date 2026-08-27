"""Central live-state aggregator.

Runs a single background loop that, every ``poll_interval_seconds``:
  1. fetches tunnel status from omr_proxy and (in real mode) per-link metrics
     from router_proxy,
  2. records samples into the metrics store,
  3. detects state transitions and writes events,
  4. publishes the fresh status to all connected SSE subscribers.

It also builds the topology graph consumed by the dashboard.
"""
from __future__ import annotations

import asyncio
import time
from typing import Optional

from config import get_settings
from schemas import (
    BondState,
    ConfigOwner,
    DashboardStatus,
    Event,
    LinkState,
    LinkStatus,
    PortForward,
    TopoEdge,
    TopoNode,
    Topology,
)
from services.metrics_store import MetricsStore, current_month
from services.omr_proxy import OmrProxy
from services.usage_collector import UsageCollector
from services.router_proxy import RouterProxy
from services.shorewall_service import ShorewallService


class Aggregator:
    def __init__(self, store: MetricsStore) -> None:
        self.settings = get_settings()
        self.store = store
        self.shorewall = ShorewallService()
        self._latest: Optional[DashboardStatus] = None
        self._subscribers: set[asyncio.Queue] = set()
        self._prev_link_state: dict[str, LinkState] = {}
        self._task: Optional[asyncio.Task] = None
        self._prune_counter = 0
        # (month, link_id, level) tuples already alerted on, so a crossed
        # data-quota threshold fires its event only once per month.
        self._usage_alerted: set[tuple[str, str, str]] = set()
        self.usage_collector = UsageCollector()
        self._prev_bond_state: Optional[BondState] = None

    # --- lifecycle ---------------------------------------------------------
    async def start(self) -> None:
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    # --- subscriptions -----------------------------------------------------
    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=10)
        self._subscribers.add(q)
        if self._latest is not None:
            q.put_nowait(self._latest)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)

    async def _publish(self, status: DashboardStatus) -> None:
        for q in list(self._subscribers):
            try:
                q.put_nowait(status)
            except asyncio.QueueFull:
                # Drop the slowest subscriber's backlog by replacing it.
                try:
                    q.get_nowait()
                    q.put_nowait(status)
                except Exception:
                    pass

    # --- main loop ---------------------------------------------------------
    async def _loop(self) -> None:
        while True:
            try:
                status = await self._collect()
                self._latest = status
                await self.store.record_links(status.links)
                await self._accumulate_usage(status)
                await self._detect_events(status)
                await self._publish(status)

                self._prune_counter += 1
                if self._prune_counter >= 360:  # ~hourly at 10s cadence
                    self._prune_counter = 0
                    await self.store.prune()
            except Exception:  # noqa: BLE001 — never let the loop die
                pass
            await asyncio.sleep(self.settings.poll_interval_seconds)

    async def _collect(self) -> DashboardStatus:
        # Create fresh proxy instances so credential overrides (R0) are always
        # picked up without requiring an aggregator restart.
        omr = OmrProxy()
        status = await omr.status()
        # In real mode, fall back to router-detected WANs when omr-admin returns
        # no link data (e.g. tunnel not yet established).
        if not self.settings.demo and not status.links:
            router = RouterProxy()
            wans = await router.detect_wans()
            status.links = [
                LinkStatus(
                    id=w.id, label=w.label or w.id, type=w.detected_type,
                    state=LinkState.up if w.up else LinkState.down,
                    enabled=w.enabled, ip=w.ip, device=w.interface or None,
                )
                for w in wans
            ]
            active = [l for l in status.links if l.state == LinkState.up]
            status.active_links = len(active)
            status.total_links = sum(1 for l in status.links if l.enabled)
        return status

    async def _emit(self, event: Event) -> None:
        """Persist an event and fan it out to the alert channels.

        Single choke point for event creation so notifications stay in sync
        with the event log without every call-site needing to know about them.
        """
        await self.store.add_event(event)
        from services import alerts_service
        await alerts_service.dispatch(event)

    async def _detect_events(self, status: DashboardStatus) -> None:
        await self._detect_bond_events(status)
        for link in status.links:
            prev = self._prev_link_state.get(link.id)
            if prev is not None and prev != link.state:
                if link.state == LinkState.down:
                    await self._emit(Event(
                        ts=int(time.time()), type="link_down",
                        detail=f"{link.label} ist ausgefallen", severity="warn"))
                elif link.state == LinkState.up:
                    await self._emit(Event(
                        ts=int(time.time()), type="link_up",
                        detail=f"{link.label} ist wieder verbunden", severity="info"))
                elif link.state == LinkState.degraded:
                    await self._emit(Event(
                        ts=int(time.time()), type="link_degraded",
                        detail=f"{link.label} ist beeinträchtigt", severity="warn"))
            self._prev_link_state[link.id] = link.state

    async def _detect_bond_events(self, status: DashboardStatus) -> None:
        """Emit an event when the overall bond changes state.

        The per-link events below say which line broke; this one says what it
        meant for the connection as a whole — going offline is the single most
        alert-worthy thing that can happen, so it gets ``error`` severity.
        """
        prev, self._prev_bond_state = self._prev_bond_state, status.state
        if prev is None or prev == status.state:
            return
        detail, severity = {
            BondState.offline: ("Verbindung offline — kein Tunnel aktiv", "error"),
            BondState.degraded: ("Verbindung beeinträchtigt — nicht alle Leitungen aktiv", "warn"),
            BondState.bonded: ("Verbindung wieder vollständig gebündelt", "info"),
        }[status.state]
        await self._emit(Event(ts=int(time.time()), type=f"bond_{status.state.value}",
                               detail=detail, severity=severity))

    async def _accumulate_usage(self, status: DashboardStatus) -> None:
        """Book this tick's traffic into the month's volume counters and fire
        one-shot events when a configured data cap threshold is crossed.

        Uses the router's cumulative interface counters where available (exact)
        and falls back to integrating throughput per link — see
        ``services/usage_collector.py``.
        """
        try:
            counters = await RouterProxy().device_stats()
        except Exception:  # noqa: BLE001 — accounting must not break the loop
            counters = {}
        rows = self.usage_collector.sample(
            status.links, counters, self.settings.poll_interval_seconds)
        month = current_month()
        if rows:
            await self.store.add_usage(month, rows)
        await self._check_quota_alerts(status, month)

    async def _check_quota_alerts(self, status: DashboardStatus, month: str) -> None:
        quotas = await self.store.quotas()
        if not quotas:
            return
        usage = await self.store.usage(month)
        labels = {l.id: l.label for l in status.links}
        # Forget thresholds tracked for past months so the set stays bounded.
        self._usage_alerted = {k for k in self._usage_alerted if k[0] == month}
        for link_id, q in quotas.items():
            cap_gb = q.get("cap_gb")
            if not cap_gb:
                continue
            cap_bytes = cap_gb * 1e9
            warn_pct = q.get("warn_pct") or 80
            rx, tx = usage.get(link_id, (0.0, 0.0))
            total = rx + tx
            label = labels.get(link_id, link_id)
            if total >= cap_bytes:
                await self._maybe_quota_event(
                    month, link_id, "cap", "error",
                    f"{label}: Monats-Datenlimit erreicht ({cap_gb:g} GB)")
            elif total >= cap_bytes * warn_pct / 100.0:
                await self._maybe_quota_event(
                    month, link_id, "warn", "warn",
                    f"{label}: {warn_pct}% des Monatslimits erreicht ({cap_gb:g} GB)")

    async def _maybe_quota_event(self, month: str, link_id: str, level: str,
                                 severity: str, detail: str) -> None:
        key = (month, link_id, level)
        if key in self._usage_alerted:
            return
        self._usage_alerted.add(key)
        await self._emit(Event(ts=int(time.time()), type=f"quota_{level}",
                               detail=detail, severity=severity))

    # --- public accessors --------------------------------------------------
    async def status(self) -> DashboardStatus:
        if self._latest is not None:
            return self._latest
        return await self._collect()

    async def refresh(self) -> DashboardStatus:
        """Recompute status immediately and push to subscribers.

        Called right after a configuration mutation (link toggle, protocol
        switch, port-forward change) so the UI reflects it without waiting for
        the next poll tick.
        """
        status = await self._collect()
        self._latest = status
        await self._detect_events(status)
        await self._publish(status)
        return status

    async def topology(self) -> Topology:
        status = await self.status()
        nodes: list[TopoNode] = []
        edges: list[TopoEdge] = []

        # WAN nodes -> router
        for link in status.links:
            state = "down" if link.state in (LinkState.down, LinkState.disabled) else (
                "degraded" if link.state == LinkState.degraded else "up")
            nodes.append(TopoNode(
                id=link.id, type="wan", label=link.label, state=state,
                owner=ConfigOwner.router,
                detail={
                    "type": link.type.value, "ip": link.ip,
                    "rx_bps": link.rx_bps, "tx_bps": link.tx_bps,
                    "latency_ms": link.latency_ms, "packet_loss_pct": link.packet_loss_pct,
                },
            ))
            edges.append(TopoEdge(
                id=f"{link.id}-router", source=link.id, target="router",
                animated=(state != "down"), bps=link.rx_bps + link.tx_bps))

        # router node
        nodes.append(TopoNode(
            id="router", type="router", label="Router", state="up",
            owner=ConfigOwner.router, detail={"role": "MPTCP peer"}))

        # tunnel edge router -> vps
        proto = status.tunnel.protocol if status.tunnel else "?"
        tunnel_up = bool(status.tunnel and status.tunnel.up)
        edges.append(TopoEdge(
            id="router-vps", source="router", target="vps",
            animated=tunnel_up, label=proto,
            bps=status.total_rx_bps + status.total_tx_bps))

        # vps node
        nodes.append(TopoNode(
            id="vps", type="vps", label="VPS", state="up" if tunnel_up else "down",
            owner=ConfigOwner.vps,
            detail={
                "protocol": proto,
                "encryption": status.tunnel.encryption if status.tunnel else None,
                "public_ip": status.vps_public_ip,
            }))

        # exit (vpn or direct internet)
        if status.exit_vpn:
            nodes.append(TopoNode(id="exit", type="exit", label=status.exit_vpn,
                                  state="up", owner=ConfigOwner.vps))
            edges.append(TopoEdge(id="vps-exit", source="vps", target="exit", animated=tunnel_up))
            nodes.append(TopoNode(id="internet", type="internet", label="Internet", state="up"))
            edges.append(TopoEdge(id="exit-internet", source="exit", target="internet", animated=tunnel_up))
        else:
            nodes.append(TopoNode(id="internet", type="internet", label="Internet", state="up"))
            edges.append(TopoEdge(id="vps-internet", source="vps", target="internet", animated=tunnel_up))

        # port forwardings as leaf nodes hanging off the VPS
        for pf in self.shorewall.list_forwards():
            if not pf.enabled:
                continue
            pid = f"pf-{pf.id}"
            label = f"Port {pf.src_port} → {pf.description or pf.dest_ip}"
            nodes.append(TopoNode(
                id=pid, type="portforward", label=label, state="up", owner=ConfigOwner.vps,
                detail={"src_port": pf.src_port, "dest": f"{pf.dest_ip}:{pf.dest_port}", "proto": pf.proto}))
            edges.append(TopoEdge(id=f"vps-{pid}", source="vps", target=pid, animated=False))

        return Topology(nodes=nodes, edges=edges)
