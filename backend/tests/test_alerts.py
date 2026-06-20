"""Tests for alert channel configuration and dispatch."""
from __future__ import annotations

import asyncio

from schemas import Event
from services import alerts_service


def test_enabled_channels_requires_all_fields():
    cfg = dict(alerts_service._DEFAULTS)
    assert alerts_service._enabled_channels(cfg) == []
    cfg.update(telegram_enabled=True, telegram_token="t", telegram_chat_id="c")
    assert alerts_service._enabled_channels(cfg) == ["telegram"]
    cfg.update(webhook_enabled=True)            # url still missing
    assert "webhook" not in alerts_service._enabled_channels(cfg)
    cfg.update(webhook_url="https://example.com/hook")
    assert "webhook" in alerts_service._enabled_channels(cfg)


def test_config_roundtrip_masks_secret(client):
    r = client.put("/alerts/config", json={
        "telegram_enabled": True, "telegram_token": "secret-token",
        "telegram_chat_id": "12345", "min_severity": "error"}).json()
    assert r["telegram_enabled"] is True
    assert r["telegram_token_set"] is True
    assert r["telegram_chat_id"] == "12345"
    assert r["min_severity"] == "error"
    assert "telegram_token" not in r          # secret never echoed

    # Disabling keeps the stored secret around.
    r = client.put("/alerts/config", json={"telegram_enabled": False}).json()
    assert r["telegram_enabled"] is False
    assert r["telegram_token_set"] is True


def test_partial_update_keeps_secret(client):
    client.put("/alerts/config", json={
        "telegram_token": "tok", "telegram_chat_id": "9"})
    r = client.put("/alerts/config", json={"telegram_chat_id": "10"}).json()
    assert r["telegram_chat_id"] == "10"
    assert r["telegram_token_set"] is True     # omitted secret preserved


def test_test_endpoint_demo_reports_sent(client):
    client.put("/alerts/config", json={
        "telegram_enabled": True, "telegram_token": "t", "telegram_chat_id": "c",
        "webhook_enabled": True, "webhook_url": "https://example.com/hook"})
    results = client.post("/alerts/test").json()["results"]
    assert results["telegram"].startswith("sent")
    assert results["webhook"].startswith("sent")


def test_dispatch_is_safe_in_demo(client):
    client.put("/alerts/config", json={
        "webhook_enabled": True, "webhook_url": "https://example.com/hook"})
    # info is below the default "warn" threshold; warn passes. Demo mode means
    # neither actually hits the network — both must complete without raising.
    asyncio.run(alerts_service.dispatch(Event(ts=0, type="t", detail="d", severity="info")))
    asyncio.run(alerts_service.dispatch(Event(ts=0, type="t", detail="d", severity="warn")))
