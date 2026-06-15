"""Tests for live status, topology and link management."""
from __future__ import annotations


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["demo"] is True


def test_status_shape(client):
    s = client.get("/dashboard/status").json()
    assert s["state"] in {"bonded", "degraded", "offline"}
    assert len(s["links"]) == 3
    assert s["total_rx_bps"] > 0
    assert s["tunnel"]["protocol"] == "glorytun_tcp"


def test_topology_graph(client):
    t = client.get("/dashboard/topology").json()
    node_types = {n["type"] for n in t["nodes"]}
    assert {"wan", "router", "vps", "internet"} <= node_types
    # every edge references existing nodes
    ids = {n["id"] for n in t["nodes"]}
    for e in t["edges"]:
        assert e["source"] in ids and e["target"] in ids


def test_disable_link_changes_state(client):
    client.put("/links/wan3", json={"enabled": False})
    s = client.get("/dashboard/status").json()
    assert s["active_links"] == 2
    assert s["total_links"] == 2
    # restore
    client.put("/links/wan3", json={"enabled": True})
    s = client.get("/dashboard/status").json()
    assert s["total_links"] == 3


def test_relabel_link(client):
    client.put("/links/wan", json={"label": "Glasfaser Haus"})
    links = client.get("/links").json()
    wan = next(l for l in links if l["id"] == "wan")
    assert wan["label"] == "Glasfaser Haus"
