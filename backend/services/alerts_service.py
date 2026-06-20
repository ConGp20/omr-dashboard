"""Alert delivery for actionable events (WAN down, data-cap thresholds, ...).

Channels: Telegram, a generic JSON webhook, and e-mail (SMTP). The channel
configuration holds secrets (bot token, SMTP password), so it is encrypted at
rest with the same machine-local key as ``settings_service`` and lives next to
it under ``data_dir`` (a Docker volume) as ``alerts.enc``.

In demo mode nothing is actually sent: the config still round-trips and the
test endpoint reports a synthetic success, so the whole alerts UI is usable
offline without leaking test messages to real chats/inboxes.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import smtplib
from email.message import EmailMessage
from typing import Any

import httpx

from config import get_settings
from schemas import AlertConfigPublic, Event
from services.settings_service import machine_key

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_log = logging.getLogger("omr_dashboard.alerts")

_SEVERITY_RANK = {"info": 0, "warn": 1, "error": 2}

# Secret fields are never echoed back to the UI and are skipped on save when
# submitted empty (so "leave blank to keep" works).
_SECRET_FIELDS = ("telegram_token", "smtp_pass")
_BOOL_FIELDS = ("telegram_enabled", "webhook_enabled", "email_enabled", "smtp_tls")

_DEFAULTS: dict[str, Any] = {
    "min_severity": "warn",
    "telegram_enabled": False,
    "telegram_token": "",
    "telegram_chat_id": "",
    "webhook_enabled": False,
    "webhook_url": "",
    "email_enabled": False,
    "smtp_host": "",
    "smtp_port": 587,
    "smtp_user": "",
    "smtp_pass": "",
    "smtp_tls": True,
    "email_from": "",
    "email_to": "",
}


def _store_path(data_dir: str) -> str:
    return os.path.join(data_dir, "alerts.enc")


def load_config(data_dir: str) -> dict[str, Any]:
    """Decrypt and return the alert config merged onto the defaults.

    Lenient: an unreadable/missing store degrades to defaults (all channels
    off) rather than failing the request.
    """
    cfg = dict(_DEFAULTS)
    path = _store_path(data_dir)
    if not os.path.exists(path):
        return cfg
    try:
        with open(path) as fh:
            blob = json.load(fh)
        key = machine_key(data_dir)
        plaintext = AESGCM(key).decrypt(
            bytes.fromhex(blob["nonce"]), bytes.fromhex(blob["data"]), None)
        stored = json.loads(plaintext)
        cfg.update({k: v for k, v in stored.items() if k in _DEFAULTS})
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        _log.warning("alerts.enc unreadable — falling back to defaults", exc_info=True)
    return cfg


def save_config(data_dir: str, updates: dict[str, Any]) -> dict[str, Any]:
    """Merge ``updates`` into the stored config and re-encrypt.

    Booleans and ``min_severity``/``smtp_port`` apply whenever provided; string
    fields apply only when non-empty so omitting a secret keeps the stored one.
    """
    cfg = load_config(data_dir)
    for k, v in updates.items():
        if k not in _DEFAULTS or v is None:
            continue
        if k in _BOOL_FIELDS or k in ("min_severity", "smtp_port"):
            cfg[k] = v
        elif isinstance(v, str) and v == "":
            continue  # keep existing (esp. secrets)
        else:
            cfg[k] = v

    key = machine_key(data_dir)
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, json.dumps(cfg).encode(), None)
    os.makedirs(data_dir, exist_ok=True)
    fd = os.open(_store_path(data_dir), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        json.dump({"nonce": nonce.hex(), "data": ciphertext.hex()}, fh)
    return cfg


def public_config(cfg: dict[str, Any]) -> AlertConfigPublic:
    """Project the stored config to the UI shape, masking secrets."""
    return AlertConfigPublic(
        min_severity=cfg.get("min_severity", "warn"),
        telegram_enabled=bool(cfg.get("telegram_enabled")),
        telegram_chat_id=cfg.get("telegram_chat_id") or None,
        telegram_token_set=bool(cfg.get("telegram_token")),
        webhook_enabled=bool(cfg.get("webhook_enabled")),
        webhook_url=cfg.get("webhook_url") or None,
        email_enabled=bool(cfg.get("email_enabled")),
        smtp_host=cfg.get("smtp_host") or None,
        smtp_port=int(cfg.get("smtp_port") or 587),
        smtp_user=cfg.get("smtp_user") or None,
        smtp_pass_set=bool(cfg.get("smtp_pass")),
        smtp_tls=bool(cfg.get("smtp_tls", True)),
        email_from=cfg.get("email_from") or None,
        email_to=cfg.get("email_to") or None,
    )


def _enabled_channels(cfg: dict[str, Any]) -> list[str]:
    out = []
    if cfg.get("telegram_enabled") and cfg.get("telegram_token") and cfg.get("telegram_chat_id"):
        out.append("telegram")
    if cfg.get("webhook_enabled") and cfg.get("webhook_url"):
        out.append("webhook")
    if cfg.get("email_enabled") and cfg.get("smtp_host") and cfg.get("email_to"):
        out.append("email")
    return out


async def dispatch(event: Event) -> None:
    """Send ``event`` to every enabled channel whose severity filter passes.

    Never raises: alerting must not be able to break the polling loop.
    """
    try:
        settings = get_settings()
        cfg = load_config(settings.data_dir)
        threshold = _SEVERITY_RANK.get(cfg.get("min_severity", "warn"), 1)
        if _SEVERITY_RANK.get(event.severity, 0) < threshold:
            return
        channels = _enabled_channels(cfg)
        if not channels:
            return
        text = f"[OMR] {event.severity.upper()}: {event.detail}"
        if settings.demo:
            _log.info("alerts(demo): would notify %s — %s", channels, text)
            return
        await asyncio.gather(
            *(_send(ch, cfg, event, text) for ch in channels),
            return_exceptions=True,
        )
    except Exception:  # noqa: BLE001 — alerting is best-effort
        _log.warning("alert dispatch failed", exc_info=True)


async def send_test(data_dir: str) -> dict[str, str]:
    """Send a test notification to each enabled channel; report per-channel.

    Returns ``{channel: "sent" | "error: ..."}``. In demo mode every enabled
    channel reports ``sent (demo)`` without touching the network.
    """
    cfg = load_config(data_dir)
    channels = _enabled_channels(cfg)
    if not channels:
        return {}
    event = Event(ts=0, type="test", detail="Test-Benachrichtigung vom OMR Dashboard",
                  severity="info")
    text = "[OMR] Test-Benachrichtigung — die Alarmierung funktioniert."
    if get_settings().demo:
        return {ch: "sent (demo)" for ch in channels}
    results: dict[str, str] = {}
    for ch in channels:
        try:
            await _send(ch, cfg, event, text)
            results[ch] = "sent"
        except Exception as exc:  # noqa: BLE001
            results[ch] = f"error: {exc}"
    return results


async def _send(channel: str, cfg: dict[str, Any], event: Event, text: str) -> None:
    if channel == "telegram":
        await _send_telegram(cfg, text)
    elif channel == "webhook":
        await _send_webhook(cfg, event, text)
    elif channel == "email":
        await asyncio.to_thread(_send_email, cfg, text)


async def _send_telegram(cfg: dict[str, Any], text: str) -> None:
    url = f"https://api.telegram.org/bot{cfg['telegram_token']}/sendMessage"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url, json={"chat_id": cfg["telegram_chat_id"], "text": text})
        resp.raise_for_status()


async def _send_webhook(cfg: dict[str, Any], event: Event, text: str) -> None:
    payload = {"text": text, "severity": event.severity, "type": event.type,
               "detail": event.detail, "ts": event.ts}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(cfg["webhook_url"], json=payload)
        resp.raise_for_status()


def _send_email(cfg: dict[str, Any], text: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = "OMR Dashboard Alert"
    msg["From"] = cfg.get("email_from") or cfg.get("smtp_user") or "omr-dashboard@localhost"
    msg["To"] = cfg["email_to"]
    msg.set_content(text)
    port = int(cfg.get("smtp_port") or 587)
    with smtplib.SMTP(cfg["smtp_host"], port, timeout=10) as smtp:
        if cfg.get("smtp_tls", True):
            smtp.starttls()
        if cfg.get("smtp_user"):
            smtp.login(cfg["smtp_user"], cfg.get("smtp_pass") or "")
        smtp.send_message(msg)
