"""Regression test for the shared-connection metrics store under concurrency.

The store keeps a single sqlite3 connection used from the thread-pool executor.
Without serialization, a metrics write racing an event write corrupts the
per-connection transaction state ("cannot commit - no transaction is active").
This drives the private sync writers from several threads at once — exactly how
``asyncio.to_thread`` schedules them — and asserts none raise.
"""
from __future__ import annotations

import threading
import time

from schemas import Event
from services.metrics_store import MetricsStore


def test_concurrent_writes_are_serialized():
    store = MetricsStore()
    errors: list[Exception] = []

    def hammer_metrics() -> None:
        try:
            for _ in range(50):
                store._insert_metrics([(int(time.time()), "wan", 1.0, 2.0, 3.0, 0.0)])
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    def hammer_events() -> None:
        try:
            for _ in range(50):
                store._insert_event(
                    Event(ts=int(time.time()), type="t", detail="d", severity="info")
                )
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=hammer_metrics) for _ in range(3)]
    threads += [threading.Thread(target=hammer_events) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    store.close()

    assert not errors, f"concurrent writes raised: {errors!r}"


def test_close_races_with_in_flight_queries():
    """close() must not pull the connection out from under a running query.

    Cancelling the poller task cannot stop work already inside
    asyncio.to_thread, so a worker can still be querying at shutdown. Before
    close() took the lock this segfaulted the interpreter; now the late calls
    have to degrade to no-ops instead.
    """
    store = MetricsStore()
    errors: list[Exception] = []
    stop = threading.Event()

    def hammer() -> None:
        try:
            while not stop.is_set():
                store._quotas()
                store._usage("2099-01")
                store._insert_event(Event(ts=1, type="t", detail="d", severity="info"))
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=hammer) for _ in range(4)]
    for t in threads:
        t.start()
    time.sleep(0.05)
    store.close()          # mid-flight, exactly as the app shutdown does it
    stop.set()
    for t in threads:
        t.join(timeout=5)

    assert not errors, f"queries racing close() raised: {errors!r}"
    # Calls after close degrade quietly rather than touching a dead connection.
    assert store._quotas() == []
    assert store._usage("2099-01") == []
    store.close()          # idempotent
