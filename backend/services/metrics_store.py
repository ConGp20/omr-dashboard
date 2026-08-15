"""Persistent time-series + event store backed by SQLite (stdlib).

A single background poller writes one sample per link every
``poll_interval_seconds``. Old rows beyond the retention window are pruned. All
DB access runs in a thread executor so it never blocks the event loop.
"""
from __future__ import annotations

import asyncio
import contextlib
import os
import sqlite3
import threading
import time
from typing import Iterator, Optional

from config import get_settings
from schemas import Event, LinkStatus, MetricPoint

_SCHEMA = """
CREATE TABLE IF NOT EXISTS link_metrics (
    ts INTEGER NOT NULL,
    link_id TEXT NOT NULL,
    rx_bps REAL, tx_bps REAL, latency_ms REAL, packet_loss_pct REAL
);
CREATE INDEX IF NOT EXISTS idx_link_metrics_ts ON link_metrics(ts);
CREATE INDEX IF NOT EXISTS idx_link_metrics_link ON link_metrics(link_id, ts);

CREATE TABLE IF NOT EXISTS events (
    ts INTEGER NOT NULL,
    type TEXT NOT NULL,
    detail TEXT,
    severity TEXT DEFAULT 'info'
);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);

CREATE TABLE IF NOT EXISTS speedtest_results (
    ts INTEGER NOT NULL,
    test_type TEXT,
    link_id TEXT,
    rx_mbps REAL, tx_mbps REAL, server TEXT
);

CREATE TABLE IF NOT EXISTS monthly_usage (
    month TEXT NOT NULL,          -- 'YYYY-MM' (UTC)
    link_id TEXT NOT NULL,
    rx_bytes REAL NOT NULL DEFAULT 0,
    tx_bytes REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (month, link_id)
);

CREATE TABLE IF NOT EXISTS link_quota (
    link_id TEXT PRIMARY KEY,
    cap_gb REAL,                  -- monthly cap in GB; NULL = no limit
    warn_pct INTEGER NOT NULL DEFAULT 80
);
"""


def current_month() -> str:
    """The current accounting month as ``YYYY-MM`` in UTC."""
    return time.strftime("%Y-%m", time.gmtime())

_PERIOD_SECONDS = {
    "1h": 3600,
    "6h": 6 * 3600,
    "24h": 24 * 3600,
    "7d": 7 * 24 * 3600,
}


class MetricsStore:
    def __init__(self) -> None:
        self.settings = get_settings()
        # The single connection is shared across the thread-pool executor, so
        # every access is serialized with this lock. sqlite3's per-connection
        # transaction state is not safe under concurrent writers otherwise
        # ("cannot commit - no transaction is active" when a poller metrics
        # write races a state-change event write).
        self._lock = threading.Lock()
        # Set by close(). Cancelling the poller task cannot stop work already
        # running inside asyncio.to_thread, so a worker can still be mid-query
        # when the app shuts down. Both accessors below check this under the
        # lock; without it the connection is closed out from under a running
        # query and the interpreter segfaults.
        self._closed = False
        os.makedirs(self.settings.data_dir, exist_ok=True)
        self._conn = sqlite3.connect(self.settings.db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # --- serialized access -------------------------------------------------
    @contextlib.contextmanager
    def _read(self) -> Iterator[Optional[sqlite3.Connection]]:
        """Hold the lock for a read; yields None once the store is closed."""
        with self._lock:
            yield None if self._closed else self._conn

    @contextlib.contextmanager
    def _write(self) -> Iterator[Optional[sqlite3.Connection]]:
        """Hold the lock for a write transaction; None once the store is closed."""
        with self._lock:
            if self._closed:
                yield None
                return
            with self._conn:
                yield self._conn

    # --- writes ------------------------------------------------------------
    async def record_links(self, links: list[LinkStatus]) -> None:
        ts = int(time.time())
        rows = [
            (ts, l.id, l.rx_bps, l.tx_bps, l.latency_ms, l.packet_loss_pct)
            for l in links
        ]
        await asyncio.to_thread(self._insert_metrics, rows)

    def _insert_metrics(self, rows: list[tuple]) -> None:
        with self._write() as conn:
            if conn is None:
                return
            conn.executemany(
                "INSERT INTO link_metrics (ts, link_id, rx_bps, tx_bps, latency_ms, packet_loss_pct)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                rows,
            )

    async def add_event(self, event: Event) -> None:
        await asyncio.to_thread(self._insert_event, event)

    def _insert_event(self, event: Event) -> None:
        with self._write() as conn:
            if conn is None:
                return
            conn.execute(
                "INSERT INTO events (ts, type, detail, severity) VALUES (?, ?, ?, ?)",
                (event.ts, event.type, event.detail, event.severity),
            )

    async def add_speedtest(self, test_type: str, link_id: Optional[str], rx: float, tx: float, server: str) -> None:
        def _ins() -> None:
            with self._write() as conn:
                if conn is None:
                    return
                conn.execute(
                    "INSERT INTO speedtest_results (ts, test_type, link_id, rx_mbps, tx_mbps, server)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (int(time.time()), test_type, link_id, rx, tx, server),
                )
        await asyncio.to_thread(_ins)

    async def add_usage(self, month: str, rows: list[tuple]) -> None:
        """Accumulate per-link byte deltas into the month's running totals.

        ``rows`` is ``[(link_id, rx_bytes, tx_bytes), ...]`` — the bytes seen in
        one poll interval. UPSERT keeps a single row per link per month.
        """
        if not rows:
            return
        await asyncio.to_thread(self._add_usage, month, rows)

    def _add_usage(self, month: str, rows: list[tuple]) -> None:
        with self._write() as conn:
            if conn is None:
                return
            conn.executemany(
                "INSERT INTO monthly_usage (month, link_id, rx_bytes, tx_bytes)"
                " VALUES (?, ?, ?, ?)"
                " ON CONFLICT(month, link_id) DO UPDATE SET"
                "   rx_bytes = rx_bytes + excluded.rx_bytes,"
                "   tx_bytes = tx_bytes + excluded.tx_bytes",
                [(month, lid, rx, tx) for (lid, rx, tx) in rows],
            )

    async def set_quota(self, link_id: str, cap_gb: Optional[float], warn_pct: int) -> None:
        await asyncio.to_thread(self._set_quota, link_id, cap_gb, warn_pct)

    def _set_quota(self, link_id: str, cap_gb: Optional[float], warn_pct: int) -> None:
        with self._write() as conn:
            if conn is None:
                return
            conn.execute(
                "INSERT INTO link_quota (link_id, cap_gb, warn_pct) VALUES (?, ?, ?)"
                " ON CONFLICT(link_id) DO UPDATE SET"
                "   cap_gb = excluded.cap_gb, warn_pct = excluded.warn_pct",
                (link_id, cap_gb, warn_pct),
            )

    # --- reads -------------------------------------------------------------
    async def usage(self, month: str) -> dict[str, tuple]:
        """Per-link accumulated ``(rx_bytes, tx_bytes)`` for ``month``."""
        rows = await asyncio.to_thread(self._usage, month)
        return {r[0]: (r[1], r[2]) for r in rows}

    def _usage(self, month: str) -> list[tuple]:
        with self._read() as conn:
            if conn is None:
                return []
            return conn.execute(
                "SELECT link_id, rx_bytes, tx_bytes FROM monthly_usage"
                " WHERE month = ? ORDER BY link_id",
                (month,),
            ).fetchall()

    async def quotas(self) -> dict[str, dict]:
        rows = await asyncio.to_thread(self._quotas)
        return {r[0]: {"cap_gb": r[1], "warn_pct": r[2]} for r in rows}

    def _quotas(self) -> list[tuple]:
        with self._read() as conn:
            if conn is None:
                return []
            return conn.execute("SELECT link_id, cap_gb, warn_pct FROM link_quota").fetchall()

    async def metrics(self, period: str) -> list[MetricPoint]:
        window = _PERIOD_SECONDS.get(period, 3600)
        since = int(time.time()) - window
        # Downsample for long windows to keep the payload reasonable.
        bucket = max(1, window // 600)  # ~600 points max
        rows = await asyncio.to_thread(self._select_metrics, since, bucket)
        return [
            MetricPoint(
                ts=r[0], link_id=r[1], rx_bps=r[2] or 0, tx_bps=r[3] or 0,
                latency_ms=r[4], packet_loss_pct=r[5],
            )
            for r in rows
        ]

    def _select_metrics(self, since: int, bucket: int) -> list[tuple]:
        with self._read() as conn:
            if conn is None:
                return []
            return conn.execute(
                "SELECT (ts/?)*? AS bucket, link_id,"
                "       AVG(rx_bps), AVG(tx_bps), AVG(latency_ms), AVG(packet_loss_pct)"
                "  FROM link_metrics WHERE ts >= ?"
                " GROUP BY bucket, link_id ORDER BY bucket ASC",
                (bucket, bucket, since),
            ).fetchall()

    async def events(self, limit: int = 50) -> list[Event]:
        rows = await asyncio.to_thread(self._select_events, limit)
        return [Event(ts=r[0], type=r[1], detail=r[2] or "", severity=r[3] or "info") for r in rows]

    def _select_events(self, limit: int) -> list[tuple]:
        with self._read() as conn:
            if conn is None:
                return []
            return conn.execute(
                "SELECT ts, type, detail, severity FROM events ORDER BY ts DESC LIMIT ?",
                (limit,),
            ).fetchall()

    async def speedtests(self, limit: int = 20) -> list[dict]:
        def _sel() -> list[tuple]:
            with self._read() as conn:
                if conn is None:
                    return []
                return conn.execute(
                    "SELECT ts, test_type, link_id, rx_mbps, tx_mbps, server"
                    " FROM speedtest_results ORDER BY ts DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        rows = await asyncio.to_thread(_sel)
        return [
            {"ts": r[0], "test_type": r[1], "link_id": r[2], "rx_mbps": r[3], "tx_mbps": r[4], "server": r[5]}
            for r in rows
        ]

    # --- maintenance -------------------------------------------------------
    async def prune(self) -> None:
        cutoff = int(time.time()) - self.settings.metrics_retention_days * 86400
        await asyncio.to_thread(self._prune, cutoff)

    def _prune(self, cutoff: int) -> None:
        # Keep monthly usage far longer than the high-resolution metrics so the
        # volume history survives — only drop months older than ~13 months.
        usage_cutoff = time.strftime("%Y-%m", time.gmtime(time.time() - 396 * 86400))
        with self._write() as conn:
            if conn is None:
                return
            conn.execute("DELETE FROM link_metrics WHERE ts < ?", (cutoff,))
            conn.execute("DELETE FROM events WHERE ts < ?", (cutoff,))
            conn.execute("DELETE FROM monthly_usage WHERE month < ?", (usage_cutoff,))

    def close(self) -> None:
        """Close the connection, waiting for any in-flight query to finish.

        Taking the lock is what makes shutdown safe: a poller thread may still
        be inside a query, and closing under it would crash the interpreter.
        """
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._conn.close()
