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


# --- schema migrations --------------------------------------------------------
def _db(tmp_path):
    from types import SimpleNamespace
    import services.metrics_store as ms
    store = ms.MetricsStore.__new__(ms.MetricsStore)
    store.settings = SimpleNamespace(data_dir=str(tmp_path), db_path=str(tmp_path / "d.db"),
                                     metrics_retention_days=7)
    return store


def test_fresh_database_lands_on_latest_version(tmp_path):
    import sqlite3
    from services.metrics_store import MIGRATIONS, MetricsStore
    conn = sqlite3.connect(str(tmp_path / "fresh.db"))
    assert MetricsStore._migrate(conn) == MIGRATIONS[-1][0]
    assert conn.execute("PRAGMA user_version").fetchone()[0] == MIGRATIONS[-1][0]
    # Idempotent: a second run applies nothing and changes nothing.
    assert MetricsStore._migrate(conn) == MIGRATIONS[-1][0]


def test_pre_versioning_database_upgrades_without_losing_rows(tmp_path):
    # Installations from before versioning existed: tables present, version 0.
    import sqlite3
    import services.metrics_store as ms
    path = str(tmp_path / "old.db")
    conn = sqlite3.connect(path)
    conn.executescript(ms._SCHEMA)
    conn.execute("INSERT INTO events (ts, type, detail) VALUES (1, 'keep', 'me')")
    conn.commit()
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 0
    assert ms.MetricsStore._migrate(conn) == ms.MIGRATIONS[-1][0]
    assert conn.execute("SELECT detail FROM events").fetchone() == ("me",)


def test_future_migration_applies_exactly_once(tmp_path, monkeypatch):
    # Simulates the next release adding a column to an existing table — the
    # case CREATE TABLE IF NOT EXISTS can never handle.
    import sqlite3
    import services.metrics_store as ms
    conn = sqlite3.connect(str(tmp_path / "m.db"))
    ms.MetricsStore._migrate(conn)                       # at version 1
    future = ms.MIGRATIONS + [(2, "ALTER TABLE events ADD COLUMN source TEXT DEFAULT 'poller';")]
    monkeypatch.setattr(ms, "MIGRATIONS", future)
    assert ms.MetricsStore._migrate(conn) == 2
    cols = [r[1] for r in conn.execute("PRAGMA table_info(events)")]
    assert "source" in cols
    # Running again must not try to add the column a second time.
    assert ms.MetricsStore._migrate(conn) == 2


def test_failed_migration_does_not_advance_version(tmp_path, monkeypatch):
    import sqlite3
    import pytest
    import services.metrics_store as ms
    conn = sqlite3.connect(str(tmp_path / "f.db"))
    ms.MetricsStore._migrate(conn)
    monkeypatch.setattr(ms, "MIGRATIONS", ms.MIGRATIONS + [(2, "ALTER TABLE nope ADD COLUMN x;")])
    with pytest.raises(sqlite3.OperationalError):
        ms.MetricsStore._migrate(conn)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
