"""Tests for overall bond-state transition events."""
from __future__ import annotations

import asyncio

from schemas import BondState, DashboardStatus, Event
from services.aggregator import Aggregator
from services.metrics_store import MetricsStore


def _transitions(*states: BondState) -> list[Event]:
    """Feed the aggregator a sequence of bond states, capturing emitted events."""
    agg = Aggregator(MetricsStore())
    seen: list[Event] = []

    async def capture(event: Event) -> None:
        seen.append(event)

    agg._emit = capture  # type: ignore[method-assign]

    async def go() -> None:
        for state in states:
            await agg._detect_bond_events(DashboardStatus(state=state, links=[]))

    try:
        asyncio.run(go())
    finally:
        agg.store.close()
    return seen


def test_first_observation_does_not_alert():
    # Startup is not a transition — otherwise every restart would page someone.
    assert _transitions(BondState.bonded) == []


def test_going_offline_is_an_error_event():
    events = _transitions(BondState.bonded, BondState.offline)
    assert len(events) == 1
    assert events[0].type == "bond_offline"
    assert events[0].severity == "error"


def test_degraded_and_recovery_are_reported():
    events = _transitions(BondState.bonded, BondState.degraded, BondState.bonded)
    assert [e.type for e in events] == ["bond_degraded", "bond_bonded"]
    assert [e.severity for e in events] == ["warn", "info"]


def test_unchanged_state_is_silent():
    assert _transitions(BondState.bonded, BondState.bonded, BondState.bonded) == []
