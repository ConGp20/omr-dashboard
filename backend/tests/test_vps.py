"""Tests for VPS endpoint management: port forwarding, exit-VPN, firewall."""
from __future__ import annotations


def test_portforward_crud(client):
    # create
    pf = client.post("/vps/portforward", json={
        "description": "OPNsense VPN", "proto": "udp", "src_port": 1194,
        "dest_ip": "192.168.100.2", "dest_port": 1194}).json()
    assert pf["id"]
    pid = pf["id"]
    # appears in list
    items = client.get("/vps/portforward").json()
    assert any(p["id"] == pid for p in items)
    # update (disable)
    upd = client.put(f"/vps/portforward/{pid}", json={
        "description": "OPNsense VPN", "proto": "udp", "src_port": 1194,
        "dest_ip": "192.168.100.2", "dest_port": 1194, "enabled": False}).json()
    assert upd["enabled"] is False
    # delete
    assert client.delete(f"/vps/portforward/{pid}").json()["success"] is True


def test_portforward_rejects_injection_dest_ip(client):
    # A dest_ip carrying extra tokens must be rejected, never written into the rule.
    r = client.post("/vps/portforward", json={
        "description": "x", "proto": "tcp", "src_port": 8080,
        "dest_ip": "192.168.100.2 -j ACCEPT", "dest_port": 80})
    assert r.status_code == 422


def test_portforward_rejects_out_of_range_port(client):
    r = client.post("/vps/portforward", json={
        "description": "x", "proto": "tcp", "src_port": 70000,
        "dest_ip": "192.168.100.2", "dest_port": 80})
    assert r.status_code == 422


def test_portforward_description_is_single_line(client):
    # Newlines in the description must be collapsed so they can't break the rule line.
    pf = client.post("/vps/portforward", json={
        "description": "evil\nDNAT net loc:1.2.3.4", "proto": "tcp",
        "src_port": 8099, "dest_ip": "192.168.100.2", "dest_port": 80}).json()
    assert "\n" not in pf["description"]
    client.delete(f"/vps/portforward/{pf['id']}")


def test_portforward_target_picker(client):
    hosts = client.get("/vps/hosts").json()
    ips = {h["ip"] for h in hosts}
    assert "192.168.100.2" in ips  # firewall host available for the picker


def test_exit_vpn_roundtrip(client):
    cfg = {"enabled": True, "type": "wireguard", "endpoint": "vpn.example:51820",
           "public_key": "PUBKEY", "private_key": "PRIVKEY", "allowed_ips": "0.0.0.0/0",
           "kill_switch": True}
    saved = client.put("/vps/exit-vpn", json=cfg).json()
    assert saved["enabled"] is True
    # private key must never be echoed back
    assert saved.get("private_key") is None
    got = client.get("/vps/exit-vpn").json()
    assert got["endpoint"] == "vpn.example:51820"


def test_nat_status(client):
    nat = client.get("/vps/nat").json()
    assert nat["public_ipv4"]
    assert isinstance(nat["tunnel_clients"], list)


def test_firewall_presets(client):
    presets = client.get("/firewall/presets").json()["presets"]
    assert any(p["id"] == "web" for p in presets)
