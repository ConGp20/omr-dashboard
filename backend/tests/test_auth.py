"""Tests for login, auth status and brute-force throttling."""
from __future__ import annotations

import auth


def test_auth_status_reports_open_in_demo(client):
    body = client.get("/auth/status").json()
    # Demo installs need no login — the UI uses this to skip the login screen
    # instead of showing a form that would accept anything.
    assert body["auth_required"] is False
    assert body["demo"] is True
    assert body["username"]


def test_login_succeeds_in_demo(client):
    body = client.post("/auth/login", json={"username": "admin", "password": "x"}).json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"


def test_me_returns_user(client):
    assert client.get("/auth/me").json()["user"] == "demo"


def test_lockout_after_repeated_failures():
    auth.reset_failures()
    ip = "203.0.113.9"
    assert auth.lockout_remaining(ip, now=1000.0) == 0
    for i in range(auth.MAX_ATTEMPTS):
        auth.record_failure(ip, now=1000.0 + i)
    assert auth.lockout_remaining(ip, now=1005.0) > 0
    # Expires once the window passes.
    assert auth.lockout_remaining(ip, now=1000.0 + auth.LOCKOUT_SECONDS + 1) == 0
    auth.reset_failures()


def test_lockout_is_per_client():
    auth.reset_failures()
    for i in range(auth.MAX_ATTEMPTS):
        auth.record_failure("198.51.100.1", now=1000.0 + i)
    assert auth.lockout_remaining("198.51.100.1", now=1005.0) > 0
    # A different client is unaffected — one attacker must not lock out the admin.
    assert auth.lockout_remaining("198.51.100.2", now=1005.0) == 0
    auth.reset_failures()


def test_success_clears_failure_history():
    auth.reset_failures()
    ip = "192.0.2.5"
    for i in range(auth.MAX_ATTEMPTS - 1):
        auth.record_failure(ip, now=1000.0 + i)
    auth.reset_failures(ip)
    assert auth.lockout_remaining(ip, now=1002.0) == 0


def test_login_returns_429_when_locked_out(client):
    auth.reset_failures()
    # The demo client always authenticates, so drive the throttle directly and
    # assert the endpoint honours it.
    for i in range(auth.MAX_ATTEMPTS):
        auth.record_failure("testclient", now=None)
    r = client.post("/auth/login", json={"username": "admin", "password": "x"})
    assert r.status_code == 429
    assert "Retry-After" in r.headers
    auth.reset_failures()
