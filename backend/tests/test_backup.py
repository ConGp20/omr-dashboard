"""Tests for encrypted backup creation, preview and restore."""
from __future__ import annotations

import io

import pytest

from services import backup_service


def test_backup_roundtrip():
    blob = backup_service.create_backup(
        password="hunter2",
        vps_config={"active_protocol": "glorytun_tcp"},
        router_config={"lan_ip": "192.168.100.1"},
        secrets={"tunnel_key": "supersecret"},
    )
    # preview works without password and hides nothing non-secret
    preview = backup_service.preview_backup(blob=blob)
    assert preview["vps"]["active_protocol"] == "glorytun_tcp"

    # correct password recovers secrets
    data = backup_service.read_backup(password="hunter2", blob=blob)
    assert data["secrets"]["tunnel_key"] == "supersecret"


def test_backup_wrong_password():
    blob = backup_service.create_backup(
        password="right", vps_config={}, router_config={}, secrets={"k": "v"})
    with pytest.raises(ValueError):
        backup_service.read_backup(password="wrong", blob=blob)


def test_backup_rejects_garbage():
    with pytest.raises(Exception):
        backup_service.read_backup(password="x", blob=b"not a backup")


def test_backup_endpoint_roundtrip(client):
    rb = client.post("/system/backup", data={"password": "secret123"})
    assert rb.status_code == 200
    assert rb.headers["content-type"] == "application/gzip"

    files = {"file": ("c.omr-backup.json.gz", io.BytesIO(rb.content), "application/gzip")}
    preview = client.post("/system/restore/preview", files=files).json()
    assert "created" in preview

    files = {"file": ("c.omr-backup.json.gz", io.BytesIO(rb.content), "application/gzip")}
    restored = client.post("/system/restore", files=files, data={"password": "secret123"}).json()
    assert restored["success"] is True


def test_backup_carries_quotas_and_alert_config(client):
    client.put("/dashboard/usage/wanB/quota", json={"cap_gb": 42, "warn_pct": 70})
    client.put("/alerts/config", json={
        "telegram_enabled": True, "telegram_token": "tok-in-backup",
        "telegram_chat_id": "555", "cooldown_minutes": 25})

    rb = client.post("/system/backup", data={"password": "pw"})
    assert rb.status_code == 200

    # Quotas are plain settings; the alert secrets ride in the encrypted part.
    preview = backup_service.preview_backup(blob=rb.content)
    assert preview["vps"]["link_quotas"]["wanB"]["cap_gb"] == 42
    assert "alerts" not in preview["vps"]
    data = backup_service.read_backup(password="pw", blob=rb.content)
    assert data["secrets"]["alerts"]["telegram_token"] == "tok-in-backup"

    # Wipe both, then restore and confirm they come back.
    client.put("/dashboard/usage/wanB/quota", json={"cap_gb": 0})
    client.put("/alerts/config", json={"telegram_enabled": False, "cooldown_minutes": 1})

    files = {"file": ("c.gz", io.BytesIO(rb.content), "application/gzip")}
    restored = client.post("/system/restore", files=files, data={"password": "pw"}).json()
    assert restored["success"] is True
    assert any("Datenlimit" in a for a in restored["applied"])
    assert "Alarm-Konfiguration" in restored["applied"]

    usage = {l["link_id"]: l for l in client.get("/dashboard/usage").json()["links"]}
    assert usage["wanB"]["cap_gb"] == 42
    assert usage["wanB"]["warn_pct"] == 70
    cfg = client.get("/alerts/config").json()
    assert cfg["telegram_enabled"] is True
    assert cfg["cooldown_minutes"] == 25
