"""Tests for metrics, diagnostics, qos, dns, config-map and router type inference."""
from __future__ import annotations

import time

from schemas import Event
from services.router_proxy import infer_type


def test_infer_type():
    assert infer_type("wwan0").value == "lte"
    assert infer_type("eth0.2", "Fiber DSL").value == "fiber"
    assert infer_type("ppp0").value == "dsl"
    assert infer_type("eth1").value == "ethernet"


def test_metrics_period_validation(client):
    assert client.get("/dashboard/metrics/24h").status_code == 200
    assert client.get("/dashboard/metrics/bogus").status_code == 400


def test_ping_returns_two_sources(client):
    r = client.post("/diagnostics/ping", json={"target": "1.1.1.1", "count": 3}).json()
    sources = {p["source"] for p in r}
    assert sources == {"router", "vps"}


def test_speedtest_records_history(client):
    client.post("/diagnostics/speedtest")
    hist = client.get("/diagnostics/speedtest/history").json()["results"]
    assert len(hist) >= 1
    assert hist[0]["rx_mbps"] > 0


def test_qos_profile_apply(client):
    r = client.put("/qos/profile", json={"active": "gaming", "available": []})
    assert r.status_code == 200
    assert client.get("/qos/profile").json()["active"] == "gaming"
    assert client.put("/qos/profile", json={"active": "nope", "available": []}).status_code == 400


def test_qos_domain_crud(client):
    rule = client.post("/qos/domains", json={"domain": "netflix.com", "target": "wan"}).json()
    assert rule["id"]
    assert any(d["domain"] == "netflix.com" for d in client.get("/qos/domains").json())
    assert client.delete(f"/qos/domains/{rule['id']}").json()["success"] is True


def test_dns_roundtrip(client):
    cfg = {"upstream": ["9.9.9.9"], "mode": "doh", "local_entries": []}
    client.put("/dns/upstream", json=cfg)
    assert client.get("/dns/upstream").json()["mode"] == "doh"


def test_config_map_three_columns(client):
    cm = client.get("/config-map").json()
    assert {"router", "vps", "sync"} <= set(cm.keys())
    assert any(item["key"] == "port_forwarding" for item in cm["vps"])
