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


def test_cooldown_suppresses_repeat_of_same_event():
    alerts_service.reset_throttle()
    ev = Event(ts=0, type="link_down", detail="LTE ist ausgefallen", severity="warn")
    assert alerts_service.should_send(ev, 10, now=1000.0) is True
    # Same event flapping seconds later -> suppressed.
    assert alerts_service.should_send(ev, 10, now=1030.0) is False
    # ... until the cooldown expires.
    assert alerts_service.should_send(ev, 10, now=1000.0 + 601) is True


def test_cooldown_never_hides_a_different_event():
    alerts_service.reset_throttle()
    down = Event(ts=0, type="link_down", detail="LTE ist ausgefallen", severity="warn")
    other = Event(ts=0, type="link_down", detail="Fiber ist ausgefallen", severity="warn")
    recovery = Event(ts=0, type="link_up", detail="LTE ist wieder verbunden", severity="info")
    assert alerts_service.should_send(down, 10, now=1000.0) is True
    # A second link failing, and the recovery notice, are new information.
    assert alerts_service.should_send(other, 10, now=1001.0) is True
    assert alerts_service.should_send(recovery, 10, now=1002.0) is True


def test_cooldown_zero_disables_throttling():
    alerts_service.reset_throttle()
    ev = Event(ts=0, type="link_down", detail="x", severity="warn")
    assert alerts_service.should_send(ev, 0, now=1000.0) is True
    assert alerts_service.should_send(ev, 0, now=1000.1) is True


def test_cooldown_roundtrips_through_config(client):
    r = client.put("/alerts/config", json={"cooldown_minutes": 30}).json()
    assert r["cooldown_minutes"] == 30
    assert client.get("/alerts/config").json()["cooldown_minutes"] == 30


def test_dispatch_is_safe_in_demo(client):
    client.put("/alerts/config", json={
        "webhook_enabled": True, "webhook_url": "https://example.com/hook"})
    # info is below the default "warn" threshold; warn passes. Demo mode means
    # neither actually hits the network — both must complete without raising.
    asyncio.run(alerts_service.dispatch(Event(ts=0, type="t", detail="d", severity="info")))
    asyncio.run(alerts_service.dispatch(Event(ts=0, type="t", detail="d", severity="warn")))
