"""Encrypted configuration backup & restore.

A backup bundles the full VPS + router configuration into a single gzip blob.
Secrets (tunnel keys, passwords) are encrypted with AES-256-GCM using a key
derived from a user-supplied password via Argon2id, so the file is safe to
store anywhere. Non-secret settings stay in clear text for transparency.
"""
from __future__ import annotations

import base64
import gzip
import json
import os
import time
from typing import Any

from argon2.low_level import Type, hash_secret_raw
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_MAGIC = "omr-backup"
_VERSION = "1.0"


def _derive_key(password: str, salt: bytes) -> bytes:
    return hash_secret_raw(
        secret=password.encode(),
        salt=salt,
        time_cost=3,
        memory_cost=64 * 1024,
        parallelism=4,
        hash_len=32,
        type=Type.ID,
    )


def _encrypt(password: str, plaintext: bytes) -> dict[str, str]:
    salt = os.urandom(16)
    nonce = os.urandom(12)
    key = _derive_key(password, salt)
    ct = AESGCM(key).encrypt(nonce, plaintext, None)
    return {
        "kdf": "argon2id",
        "salt": base64.b64encode(salt).decode(),
        "nonce": base64.b64encode(nonce).decode(),
        "data": base64.b64encode(ct).decode(),
    }


def _decrypt(password: str, blob: dict[str, str]) -> bytes:
    salt = base64.b64decode(blob["salt"])
    nonce = base64.b64decode(blob["nonce"])
    key = _derive_key(password, salt)
    ct = base64.b64decode(blob["data"])
    return AESGCM(key).decrypt(nonce, ct, None)


def create_backup(
    *,
    password: str,
    vps_config: dict[str, Any],
    router_config: dict[str, Any],
    secrets: dict[str, Any],
) -> bytes:
    """Return a gzip-compressed encrypted backup blob."""
    payload = {
        "magic": _MAGIC,
        "version": _VERSION,
        "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "vps": vps_config,
        "router": router_config,
        "credentials": {
            "encrypted": True,
            **_encrypt(password, json.dumps(secrets).encode()),
        },
    }
    return gzip.compress(json.dumps(payload).encode())


def _load_payload(blob: bytes) -> dict[str, Any]:
    """Decompress + parse a backup blob, mapping any malformed input to a clean
    ValueError so callers return 400 (bad upload), never an unhandled 500."""
    try:
        payload = json.loads(gzip.decompress(blob))
    except Exception as exc:  # noqa: BLE001 — any corrupt/non-gzip/non-json input
        raise ValueError("Keine gültige OMR-Backup-Datei") from exc
    if not isinstance(payload, dict) or payload.get("magic") != _MAGIC:
        raise ValueError("Keine gültige OMR-Backup-Datei")
    return payload


def read_backup(*, password: str, blob: bytes) -> dict[str, Any]:
    """Decode and decrypt a backup blob into its components."""
    payload = _load_payload(blob)
    creds = payload.get("credentials", {})
    secrets: dict[str, Any] = {}
    if creds.get("encrypted"):
        try:
            secrets = json.loads(_decrypt(password, creds))
        except Exception as exc:  # noqa: BLE001
            raise ValueError("Falsches Passwort oder beschädigte Datei") from exc
    return {
        "created": payload.get("created"),
        "vps": payload.get("vps", {}),
        "router": payload.get("router", {}),
        "secrets": secrets,
    }


def preview_backup(*, blob: bytes) -> dict[str, Any]:
    """Return non-secret metadata without needing the password."""
    payload = _load_payload(blob)
    return {
        "created": payload.get("created"),
        "version": payload.get("version"),
        "vps": payload.get("vps", {}),
        "router": payload.get("router", {}),
    }
