"""Encrypted, persisted overrides for connection/security settings.

Credentials set once during the wizard (router IP/user/pass, OMR admin key,
JWT secret, dashboard user/password) need to stay editable afterwards without
touching ``.env`` and recreating the container — see
``docs/routing-plan.de.md`` §8 for the audit this implements.

Overrides are encrypted at rest with a machine-local key, not a user-supplied
password: the backend must be able to decrypt them unattended on every
restart. The key lives next to the encrypted blob under ``data_dir`` (which is
a Docker volume, so it survives container recreation) with file mode 0600.
This is a different threat model than ``backup_service.py``'s password-based
export — these overrides never leave the host.
"""
from __future__ import annotations

import json
import os
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

OVERRIDABLE_FIELDS = (
    "router_ip",
    "router_user",
    "router_pass",
    "omr_admin_key",
    "jwt_secret",
    "dashboard_user",
    "dashboard_pass",
)
SECRET_FIELDS = {"router_pass", "omr_admin_key", "jwt_secret", "dashboard_pass"}


def _key_path(data_dir: str) -> str:
    return os.path.join(data_dir, "settings.key")


def _store_path(data_dir: str) -> str:
    return os.path.join(data_dir, "settings.enc")


def _load_or_create_key(data_dir: str) -> bytes:
    os.makedirs(data_dir, exist_ok=True)
    path = _key_path(data_dir)
    if os.path.exists(path):
        with open(path, "rb") as fh:
            return fh.read()
    key = AESGCM.generate_key(bit_length=256)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(key)
    return key


def machine_key(data_dir: str) -> bytes:
    """The 256-bit machine-local key used for encrypted-at-rest stores.

    Shared with ``alerts_service`` so both encrypt their blobs with the same
    unattended key (see module docstring for the threat model)."""
    return _load_or_create_key(data_dir)


class SettingsStoreError(RuntimeError):
    """The store file exists but can't be decrypted (corrupt file, lost key,
    ...). Writes must raise this instead of silently treating it as empty —
    otherwise a transient read failure on the read-merge-write path in
    save_overrides() would permanently destroy every previously stored
    credential on the very next save."""


def _load_overrides_or_raise(data_dir: str) -> dict[str, Any]:
    path = _store_path(data_dir)
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as fh:
            blob = json.load(fh)
        key = _load_or_create_key(data_dir)
        nonce = bytes.fromhex(blob["nonce"])
        ciphertext = bytes.fromhex(blob["data"])
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, None)
        data = json.loads(plaintext)
        return {k: v for k, v in data.items() if k in OVERRIDABLE_FIELDS}
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise SettingsStoreError(
            "Gespeicherte Zugangsdaten konnten nicht entschlüsselt werden "
            "(settings.enc/settings.key beschädigt oder inkonsistent)."
        ) from exc


def load_overrides(data_dir: str) -> dict[str, Any]:
    """Decrypt and return persisted overrides, or {} if none/unreadable.

    Lenient on purpose: reads (GET endpoints, config.get_settings()) should
    degrade to env defaults rather than fail the whole request. Writes use
    _load_overrides_or_raise() instead so a read failure can't masquerade as
    "no overrides yet" and wipe them out.
    """
    try:
        return _load_overrides_or_raise(data_dir)
    except SettingsStoreError:
        return {}


def save_overrides(data_dir: str, updates: dict[str, Any]) -> dict[str, Any]:
    """Merge ``updates`` into the persisted overrides and re-encrypt.

    Only known overridable fields with a non-None value are merged in, so a
    PUT that omits a field (or sends it as null) leaves the existing value
    untouched. Returns the merged override set. Raises SettingsStoreError
    (instead of silently losing data) if the existing store can't be read.
    """
    current = _load_overrides_or_raise(data_dir)
    current.update({
        k: v for k, v in updates.items()
        if k in OVERRIDABLE_FIELDS and v is not None and v != ""
    })
    key = _load_or_create_key(data_dir)
    nonce = os.urandom(12)
    plaintext = json.dumps(current).encode()
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)
    blob = {"nonce": nonce.hex(), "data": ciphertext.hex()}
    os.makedirs(data_dir, exist_ok=True)
    fd = os.open(_store_path(data_dir), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        json.dump(blob, fh)
    return current


def overridden_fields(data_dir: str) -> set[str]:
    return set(load_overrides(data_dir).keys())
