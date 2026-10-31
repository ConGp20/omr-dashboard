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


def test_month_progress_is_a_sane_fraction():
    import calendar
    import time as _time
    from services.metrics_store import month_progress

    # Mid-month reference point: 2099-06-16 12:00 UTC -> 15.5/30 days.
    ts = calendar.timegm(_time.struct_time((2099, 6, 16, 12, 0, 0, 0, 0, 0)))
    fraction, day, days = month_progress(ts)
    assert (day, days) == (16, 30)
    assert abs(fraction - 15.5 / 30) < 0.001

    # First instant of a month must not divide by zero.
    ts = calendar.timegm(_time.struct_time((2099, 6, 1, 0, 0, 0, 0, 0, 0)))
    fraction, day, days = month_progress(ts)
    assert fraction > 0 and day == 1


def test_usage_endpoint_projects_month_end(client):
    body = client.get("/dashboard/usage").json()
    assert 1 <= body["day_of_month"] <= 31
    assert body["days_in_month"] in (28, 29, 30, 31)
    for link in body["links"]:
        # Projection is never below what is already used.
        assert link["projected_bytes"] >= link["total_bytes"] - 1


def test_quota_can_be_cleared(client):
    client.put("/dashboard/usage/wanC/quota", json={"cap_gb": 10})
    cleared = client.put("/dashboard/usage/wanC/quota", json={"cap_gb": 0}).json()
    assert cleared["cap_gb"] is None
    assert cleared["used_pct"] is None
    assert cleared["over_warn"] is False
