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
