"""Tests for protocol listing, switching and schedulers."""
from __future__ import annotations


def test_list_protocols_has_metadata(client):
    protocols = client.get("/protocols").json()
    gt = next(p for p in protocols if p["id"] == "glorytun_tcp")
    assert gt["active"] is True
    assert gt["good_for"]      # plain-language guidance present
    assert gt["avoid_when"]
    assert gt["vps_port"] == 65001


def test_recommendation_present(client):
    protocols = client.get("/protocols").json()
    assert any(p["recommended"] for p in protocols)


def test_switch_protocol(client):
    r = client.post("/protocols/switch", json={"protocol": "shadowsocks"})
    assert r.status_code == 200
    assert r.json()["protocol"] == "shadowsocks"
    # an event should be recorded
    events = client.get("/dashboard/events").json()
    assert any(e["type"] == "protocol_switch" for e in events)


def test_schedulers_listed(client):
    sched = client.get("/protocols/schedulers").json()["schedulers"]
    ids = {s["id"] for s in sched}
    assert {"default", "redundant", "fullmesh"} <= ids
    assert all(s["description"] for s in sched)


def test_reject_unknown_scheduler(client):
    r = client.put("/protocols/scheduler", json={"scheduler": "bogus"})
    assert r.status_code == 400
