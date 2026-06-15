"""Persistent time-series + event store backed by SQLite (stdlib).

A single background poller writes one sample per link every
``poll_interval_seconds``. Old rows beyond the retention window are pruned. All
DB access runs in a thread executor so it never blocks the event loop.
"""
from __future__ import annotations

import asyncio
import os
import sqlite3
import time
from typing import Optional

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
"""

_PERIOD_SECONDS = {
    "1h": 3600,
    "6h": 6 * 3600,
    "24h": 24 * 3600,
    "7d": 7 * 24 * 3600,
}


class MetricsStore:
    def __init__(self) -> None:
        self.settings = get_settings()
        os.makedirs(self.settings.data_dir, exist_ok=True)
        self._conn = sqlite3.connect(self.settings.db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # --- writes ------------------------------------------------------------
    async def record_links(self, links: list[LinkStatus]) -> None:
        ts = int(time.time())
        rows = [
            (ts, l.id, l.rx_bps, l.tx_bps, l.latency_ms, l.packet_loss_pct)
            for l in links
        ]
        await asyncio.to_thread(self._insert_metrics, rows)

    def _insert_metrics(self, rows: list[tuple]) -> None:
        with self._conn:
            self._conn.executemany(
                "INSERT INTO link_metrics (ts, link_id, rx_bps, tx_bps, latency_ms, packet_loss_pct)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                rows,
            )

    async def add_event(self, event: Event) -> None:
        await asyncio.to_thread(self._insert_event, event)

    def _insert_event(self, event: Event) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO events (ts, type, detail, severity) VALUES (?, ?, ?, ?)",
                (event.ts, event.type, event.detail, event.severity),
            )

    async def add_speedtest(self, test_type: str, link_id: Optional[str], rx: float, tx: float, server: str) -> None:
        def _ins() -> None:
            with self._conn:
                self._conn.execute(
                    "INSERT INTO speedtest_results (ts, test_type, link_id, rx_mbps, tx_mbps, server)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (int(time.time()), test_type, link_id, rx, tx, server),
                )
        await asyncio.to_thread(_ins)

    # --- reads -------------------------------------------------------------
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
        cur = self._conn.execute(
            "SELECT (ts/?)*? AS bucket, link_id,"
            "       AVG(rx_bps), AVG(tx_bps), AVG(latency_ms), AVG(packet_loss_pct)"
            "  FROM link_metrics WHERE ts >= ?"
            " GROUP BY bucket, link_id ORDER BY bucket ASC",
            (bucket, bucket, since),
        )
        return cur.fetchall()

    async def events(self, limit: int = 50) -> list[Event]:
        rows = await asyncio.to_thread(self._select_events, limit)
        return [Event(ts=r[0], type=r[1], detail=r[2] or "", severity=r[3] or "info") for r in rows]

    def _select_events(self, limit: int) -> list[tuple]:
        cur = self._conn.execute(
            "SELECT ts, type, detail, severity FROM events ORDER BY ts DESC LIMIT ?",
            (limit,),
        )
        return cur.fetchall()

    async def speedtests(self, limit: int = 20) -> list[dict]:
        def _sel() -> list[tuple]:
            cur = self._conn.execute(
                "SELECT ts, test_type, link_id, rx_mbps, tx_mbps, server"
                " FROM speedtest_results ORDER BY ts DESC LIMIT ?",
                (limit,),
            )
            return cur.fetchall()
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
        with self._conn:
            self._conn.execute("DELETE FROM link_metrics WHERE ts < ?", (cutoff,))
            self._conn.execute("DELETE FROM events WHERE ts < ?", (cutoff,))

    def close(self) -> None:
        self._conn.close()
