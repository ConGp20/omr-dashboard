"""Tests for the setup wizard flow."""
from __future__ import annotations


def test_connect(client):
    r = client.post("/wizard/connect", json={"vps_ip": "1.2.3.4", "omr_key": "key"}).json()
    assert r["success"] is True
    assert "glorytun_tcp" in r["protocols_available"]


def test_detect_wans(client):
    r = client.post("/wizard/detect-wans", json={
        "router_ip": "192.168.100.1", "router_user": "root", "router_pass": "x"}).json()
    assert len(r["wans"]) == 3
    types = {w["detected_type"] for w in r["wans"]}
    assert "fiber" in types and "lte" in types


def test_apply(client):
    wans = client.post("/wizard/detect-wans", json={
        "router_ip": "192.168.100.1", "router_user": "root", "router_pass": "x"}).json()["wans"]
    r = client.post("/wizard/apply", json={
        "vps_ip": "1.2.3.4", "omr_key": "key", "router_ip": "192.168.100.1",
        "protocol": "glorytun_tcp", "wans": wans}).json()
    assert r["success"] is True
    assert r["download_mbps"] > 0
    assert any(s["step"].startswith("Tunnel") for s in r["steps"])
