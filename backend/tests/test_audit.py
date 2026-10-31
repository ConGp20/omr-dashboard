"""Tests for the configuration audit trail and the usage CSV export."""
from __future__ import annotations

from services import audit


def test_only_mutating_requests_are_audited():
    assert audit.should_audit("PUT", "/alerts/config") is True
    assert audit.should_audit("POST", "/vps/portforward") is True
    assert audit.should_audit("DELETE", "/qos/domains/1") is True
    # Reads change nothing — auditing them would bury the changes in polling.
    assert audit.should_audit("GET", "/dashboard/status") is False
    assert audit.should_audit("HEAD", "/health") is False


def test_read_only_actions_with_a_write_verb_are_skipped():
    # These POST but mutate nothing; they would be pure noise in the trail.
    for path in ("/diagnostics/ping", "/diagnostics/speedtest",
                 "/alerts/test", "/settings/connection/test"):
        assert audit.should_audit("POST", path) is False, path


def test_changes_are_recorded_with_actor_and_status(client):
    client.put("/dashboard/usage/wanAudit/quota", json={"cap_gb": 5})
    entries = client.get("/system/audit").json()["entries"]
    match = [e for e in entries if e["path"].endswith("/wanAudit/quota")]
    assert match, f"change not recorded; got {entries[:3]}"
    entry = match[0]
    assert entry["method"] == "PUT"
    assert entry["status"] == 200
    assert entry["actor"] == "demo"
    assert entry["ts"] > 0


def test_reads_do_not_appear_in_the_trail(client):
    client.get("/dashboard/status")
    entries = client.get("/system/audit").json()["entries"]
    assert not any(e["path"] == "/dashboard/status" for e in entries)


def test_audit_never_stores_bodies_or_query_strings(client):
    # A secret in the body must not end up in a table meant to be safe to read.
    client.put("/alerts/config", json={"telegram_token": "super-secret-token"})
    entries = client.get("/system/audit").json()["entries"]
    assert not any("super-secret-token" in str(e.values()) for e in entries)
    assert any(e["path"] == "/alerts/config" for e in entries)


def test_audit_limit_is_clamped(client):
    assert len(client.get("/system/audit?limit=1").json()["entries"]) <= 1
    # Out-of-range values must not blow up or dump the whole table.
    assert client.get("/system/audit?limit=99999").status_code == 200
    assert client.get("/system/audit?limit=0").status_code == 200


def test_usage_csv_export(client):
    client.put("/dashboard/usage/wanCsv/quota", json={"cap_gb": 12})
    res = client.get("/dashboard/usage.csv")
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert "attachment" in res.headers["content-disposition"]

    lines = res.text.strip().splitlines()
    assert lines[0].startswith("month;link_id;label")
    row = [l for l in lines if ";wanCsv;" in l]
    assert row, f"link missing from export: {lines}"
    assert ";12;" in row[0]      # the cap column
