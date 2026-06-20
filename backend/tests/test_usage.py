"""Tests for monthly per-WAN data usage tracking."""
from __future__ import annotations

import asyncio

import deps
from services.metrics_store import MetricsStore, current_month


def test_usage_accumulates_and_quota_roundtrip():
    store = MetricsStore()
    month = "2099-01"  # fixed test month, never touched by the live poller
    asyncio.run(store.add_usage(month, [("wanX", 1e9, 0.5e9)]))
    asyncio.run(store.add_usage(month, [("wanX", 1e9, 0.5e9)]))
    usage = asyncio.run(store.usage(month))
    assert usage["wanX"] == (2e9, 1e9)

    asyncio.run(store.set_quota("wanX", 50.0, 75))
    quotas = asyncio.run(store.quotas())
    assert quotas["wanX"]["cap_gb"] == 50.0
    assert quotas["wanX"]["warn_pct"] == 75

    asyncio.run(store.set_quota("wanX", None, 90))  # clear cap
    assert asyncio.run(store.quotas())["wanX"]["cap_gb"] is None
    store.close()


def test_usage_endpoint_lists_links(client):
    body = client.get("/dashboard/usage").json()
    assert body["month"] == current_month()
    ids = {l["link_id"] for l in body["links"]}
    assert "wan" in ids  # demo links surface via current status labels


def test_quota_endpoint_flags_warn_and_cap(client):
    # Seed a dedicated link the live demo poller never touches, so the math is
    # deterministic: 0.9 GB used against a 1 GB cap at 80% warn -> over warn.
    asyncio.run(deps.get_store().add_usage(current_month(), [("wanT", 0.9e9, 0.0)]))
    body = client.put("/dashboard/usage/wanT/quota",
                      json={"cap_gb": 1, "warn_pct": 80}).json()
    assert body["cap_gb"] == 1.0
    assert body["over_warn"] is True
    assert body["over_cap"] is False
    assert 89.0 < body["used_pct"] < 91.0

    listing = client.get("/dashboard/usage").json()
    assert any(l["link_id"] == "wanT" for l in listing["links"])


def test_quota_can_be_cleared(client):
    client.put("/dashboard/usage/wanC/quota", json={"cap_gb": 10})
    cleared = client.put("/dashboard/usage/wanC/quota", json={"cap_gb": 0}).json()
    assert cleared["cap_gb"] is None
    assert cleared["used_pct"] is None
    assert cleared["over_warn"] is False
