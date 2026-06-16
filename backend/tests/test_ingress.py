"""Tests for ingress granularity (R2): port ranges, weighted multi-target
load balancing, source CIDR filters, rate limiting. These extend the plain
PortForward additively — see services/shorewall_service.py."""
from __future__ import annotations


def test_portforward_port_range(client):
    pf = client.post("/vps/portforward", json={
        "description": "Game server range", "proto": "udp",
        "src_port": 27000, "src_port_end": 27010,
        "dest_ip": "192.168.100.20", "dest_port": 27000,
    }).json()
    assert pf["src_port_end"] == 27010
    client.delete(f"/vps/portforward/{pf['id']}")


def test_portforward_rejects_inverted_range(client):
    r = client.post("/vps/portforward", json={
        "description": "x", "proto": "tcp", "src_port": 8000, "src_port_end": 7000,
        "dest_ip": "192.168.100.2", "dest_port": 80,
    })
    assert r.status_code == 422


def test_portforward_weighted_targets(client):
    pf = client.post("/vps/portforward", json={
        "description": "LB", "proto": "tcp", "src_port": 8080,
        "dest_ip": "192.168.100.10", "dest_port": 80,
        "extra_targets": [{"dest_ip": "192.168.100.11", "dest_port": 80, "weight": 3}],
    }).json()
    assert pf["extra_targets"][0]["weight"] == 3
    client.delete(f"/vps/portforward/{pf['id']}")


def test_portforward_src_cidr_and_rate_limit(client):
    pf = client.post("/vps/portforward", json={
        "description": "Restricted", "proto": "tcp", "src_port": 9000,
        "dest_ip": "192.168.100.5", "dest_port": 9000,
        "allow_src_cidrs": ["203.0.113.0/24"],
        "deny_src_cidrs": ["203.0.113.99/32"],
        "rate_limit_per_min": 60,
    }).json()
    assert pf["allow_src_cidrs"] == ["203.0.113.0/24"]
    assert pf["deny_src_cidrs"] == ["203.0.113.99/32"]
    assert pf["rate_limit_per_min"] == 60
    client.delete(f"/vps/portforward/{pf['id']}")


def test_portforward_rejects_invalid_cidr(client):
    r = client.post("/vps/portforward", json={
        "description": "x", "proto": "tcp", "src_port": 9001,
        "dest_ip": "192.168.100.5", "dest_port": 9001,
        "allow_src_cidrs": ["not-a-cidr"],
    })
    assert r.status_code == 422


def test_shorewall_render_and_reparse_roundtrip(tmp_path, monkeypatch):
    """Exercise the real (non-demo) file-based renderer/parser directly,
    since the API tests above run in demo mode (in-memory store)."""
    import config
    from services import shorewall_service
    from schemas import IngressTarget, PortForward

    monkeypatch.setenv("OMR_DASHBOARD_DEMO", "false")
    rules_path = tmp_path / "rules"
    monkeypatch.setenv("OMR_DASHBOARD_SHOREWALL_RULES", str(rules_path))
    config.get_settings.cache_clear()

    svc = shorewall_service.ShorewallService()
    pf = PortForward(
        description="LB with range and filters", proto="tcp",
        src_port=8000, src_port_end=8005,
        dest_ip="192.168.100.10", dest_port=80,
        extra_targets=[IngressTarget(dest_ip="192.168.100.11", dest_port=80, weight=2)],
        allow_src_cidrs=["203.0.113.0/24"],
        deny_src_cidrs=["203.0.113.99/32"],
        rate_limit_per_min=120,
    )
    saved = svc.add_forward(pf)

    reloaded = shorewall_service.ShorewallService().list_forwards()
    found = next(f for f in reloaded if f.id == saved.id)
    assert found.src_port == 8000
    assert found.src_port_end == 8005
    assert found.dest_ip == "192.168.100.10"
    assert len(found.extra_targets) == 1
    assert found.extra_targets[0].dest_ip == "192.168.100.11"
    assert found.extra_targets[0].weight == 2
    assert found.allow_src_cidrs == ["203.0.113.0/24"]
    assert found.deny_src_cidrs == ["203.0.113.99/32"]
    assert found.rate_limit_per_min == 120

    # monkeypatch reverts the env vars after the test; restore the cache too
    # so subsequent tests see demo settings again.
    monkeypatch.undo()
    config.get_settings.cache_clear()
