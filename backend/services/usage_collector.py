"""Turns successive interface byte counters into per-link usage deltas.

Volume accounting prefers the router's cumulative rx/tx byte counters: they are
maintained by the kernel and therefore exact. Integrating sampled throughput
instead — the previous approach — silently loses everything that happens
between two polls and drifts over a month.

Counters are cumulative and reset to zero when the router (or the interface)
restarts, so a decrease is treated as a reset: the baseline is re-armed and no
traffic is booked for that tick. Links whose device exposes no counter fall
back to integrating the reported rate, so accounting never stops entirely.
"""
from __future__ import annotations

from schemas import LinkState, LinkStatus

# One tick's traffic per link, as (link_id, rx_bytes, tx_bytes).
UsageRows = list[tuple[str, float, float]]


class UsageCollector:
    def __init__(self) -> None:
        # device -> last seen (rx_bytes, tx_bytes)
        self._prev: dict[str, tuple[float, float]] = {}

    def sample(
        self,
        links: list[LinkStatus],
        counters: dict[str, tuple[float, float]],
        interval_seconds: float,
    ) -> UsageRows:
        """Return the traffic to book for this tick, one row per active link."""
        rows: UsageRows = []
        for link in links:
            if not link.enabled or link.state == LinkState.disabled:
                continue
            counter = counters.get(link.device) if link.device else None
            if counter is not None:
                delta = self._delta(link.device, counter)
            else:
                # No kernel counter for this link — integrate the sampled rate.
                delta = (
                    max(0.0, link.rx_bps) * interval_seconds / 8.0,
                    max(0.0, link.tx_bps) * interval_seconds / 8.0,
                )
            if delta[0] or delta[1]:
                rows.append((link.id, delta[0], delta[1]))
        return rows

    def _delta(self, device: str, current: tuple[float, float]) -> tuple[float, float]:
        previous = self._prev.get(device)
        self._prev[device] = current
        if previous is None:
            # First observation only establishes the baseline — booking the
            # absolute counter here would charge a month for all traffic since
            # the router last booted.
            return (0.0, 0.0)
        rx = current[0] - previous[0]
        tx = current[1] - previous[1]
        if rx < 0 or tx < 0:
            # Counter reset (reboot / interface reinit): re-arm, book nothing.
            return (0.0, 0.0)
        return (rx, tx)

    def forget(self, device: str) -> None:
        """Drop a device's baseline (e.g. link removed from the config)."""
        self._prev.pop(device, None)
