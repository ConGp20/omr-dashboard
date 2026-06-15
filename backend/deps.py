"""Shared singletons wired up at application startup.

Kept in a dedicated module so routers can import accessors without creating
circular imports with the FastAPI app module.
"""
from __future__ import annotations

from typing import Optional

from services.aggregator import Aggregator
from services.metrics_store import MetricsStore

_store: Optional[MetricsStore] = None
_aggregator: Optional[Aggregator] = None


def init(store: MetricsStore, aggregator: Aggregator) -> None:
    global _store, _aggregator
    _store = store
    _aggregator = aggregator


def get_store() -> MetricsStore:
    assert _store is not None, "MetricsStore not initialised"
    return _store


def get_aggregator() -> Aggregator:
    assert _aggregator is not None, "Aggregator not initialised"
    return _aggregator
