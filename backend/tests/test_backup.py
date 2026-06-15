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
