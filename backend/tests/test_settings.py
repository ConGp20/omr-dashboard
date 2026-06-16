"""Tests for the post-setup settings overrides (R0)."""
from __future__ import annotations


def test_connection_settings_roundtrip(client):
    before = client.get("/settings/connection").json()
    assert before["router_pass_set"] is False
    assert before["overridden"] == []

    updated = client.put("/settings/connection", json={
        "router_ip": "192.168.50.1", "router_user": "root", "router_pass": "s3cret",
    }).json()
    assert updated["router_ip"] == "192.168.50.1"
    assert updated["router_pass_set"] is True
    assert set(updated["overridden"]) >= {"router_ip", "router_user", "router_pass"}

    # GET reflects the persisted override, and the secret itself is never echoed back.
    again = client.get("/settings/connection").json()
    assert again["router_ip"] == "192.168.50.1"
    assert "router_pass" not in again


def test_connection_settings_partial_update_preserves_secret(client):
    client.put("/settings/connection", json={"router_pass": "first-secret"})
    # A later update that omits router_pass must not clear the stored secret.
    updated = client.put("/settings/connection", json={"router_ip": "10.0.0.9"}).json()
    assert updated["router_ip"] == "10.0.0.9"
    assert updated["router_pass_set"] is True


def test_connection_test_demo_mode(client):
    result = client.post("/settings/connection/test").json()
    assert result["router_reachable"] is True
    assert result["omr_admin_reachable"] is True


def test_security_settings_roundtrip(client):
    updated = client.put("/settings/security", json={
        "dashboard_user": "ops", "jwt_secret": "a-long-random-value",
    }).json()
    assert updated["dashboard_user"] == "ops"
    assert updated["jwt_secret_set"] is True

    again = client.get("/settings/security").json()
    assert again["dashboard_user"] == "ops"
    assert "jwt_secret" not in again
