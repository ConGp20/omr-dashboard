"""Tests for the setup wizard flow."""
from __future__ import annotations

import asyncio

from services.omr_proxy import OmrProxy, build_key_directives


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
    # The router config step reports that VPS IP + keys were transferred.
    assert any("Schlüssel" in s["step"] and s["ok"] for s in r["steps"])


def test_tunnel_secrets_demo_returns_keys(client):
    secrets = asyncio.run(OmrProxy().tunnel_secrets())
    # Demo mode exposes the credential the router needs plus per-protocol keys.
    assert secrets["user_password"]
    assert secrets["shadowsocks_key"]
    assert secrets["glorytun_key"]


def test_build_key_directives_shadowsocks():
    secrets = {"shadowsocks_key": "abc123"}
    directives = build_key_directives("shadowsocks", secrets, vps_ip="1.2.3.4")
    assert len(directives) == 1
    d = directives[0]
    # Verified against the upstream LuCI wizard: shadowsocks-libev.sss0.key.
    assert d["config"] == "shadowsocks-libev"
    assert d["section"] == "sss0"
    assert d["values"]["key"] == "abc123"
    assert d["values"]["server"] == "1.2.3.4"


def test_build_key_directives_vpn_protocol_uses_retrieve():
    # Glorytun/WireGuard keys are pulled by the router via forceretrieve,
    # so no explicit UCI directive is produced here.
    assert build_key_directives("glorytun_tcp", {"glorytun_key": "x"}, "1.2.3.4") == []
    assert build_key_directives("wireguard", {}, "1.2.3.4") == []


def test_build_key_directives_missing_secret_is_skipped():
    assert build_key_directives("shadowsocks", {}, "1.2.3.4") == []
