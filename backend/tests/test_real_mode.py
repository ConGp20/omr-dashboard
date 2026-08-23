"""Real-mode tests for paths the demo-mode suite never executes.

The global conftest runs everything with OMR_DASHBOARD_DEMO=true, which is
exactly how a demo-only stub once shipped as a "working" feature. These tests
patch real-mode settings into the units that can be exercised without a live
VPS/router: authentication and the omr-admin secret extraction that the wizard
key transfer depends on.
"""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

import auth
from services.omr_proxy import OmrProxy


def _real_settings(**over):
    base = dict(demo=False, dashboard_user="admin", dashboard_pass="secret-pw",
                omr_admin_key="", jwt_secret="unit-test-secret", jwt_ttl_minutes=60)
    base.update(over)
    return SimpleNamespace(**base)


@pytest.fixture()
def real_auth(monkeypatch):
    settings = _real_settings()
    monkeypatch.setattr(auth, "get_settings", lambda: settings)
    return settings


# --- authentication with a password actually set ----------------------------
def test_real_mode_requires_a_token(real_auth):
    with pytest.raises(HTTPException) as exc:
        asyncio.run(auth.require_user(creds=None))
    assert exc.value.status_code == 401


def test_real_mode_rejects_garbage_token(real_auth):
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="not-a-jwt")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(auth.require_user(creds=creds))
    assert exc.value.status_code == 401


def test_real_mode_full_token_roundtrip(real_auth):
    assert auth.verify_credentials("admin", "secret-pw") is True
    token = auth.create_token("admin")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    assert asyncio.run(auth.require_user(creds=creds)) == "admin"


def test_real_mode_rejects_wrong_password_and_wrong_user(real_auth):
    assert auth.verify_credentials("admin", "wrong") is False
    assert auth.verify_credentials("root", "secret-pw") is False


def test_token_signed_with_other_secret_is_rejected(real_auth, monkeypatch):
    token = auth.create_token("admin")
    monkeypatch.setattr(auth, "get_settings",
                        lambda: _real_settings(jwt_secret="rotated"))
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with pytest.raises(HTTPException):
        asyncio.run(auth.require_user(creds=creds))


def test_auth_required_flag_matches_reality(monkeypatch):
    monkeypatch.setattr(auth, "get_settings", lambda: _real_settings())
    assert auth.auth_required() is True
    # Fresh install, nothing set: open on purpose — and the UI must know.
    monkeypatch.setattr(auth, "get_settings",
                        lambda: _real_settings(dashboard_pass="", omr_admin_key=""))
    assert auth.auth_required() is False
    # Falls back to the admin key when only that is set.
    monkeypatch.setattr(auth, "get_settings",
                        lambda: _real_settings(dashboard_pass="", omr_admin_key="k"))
    assert auth.auth_required() is True
    assert auth.verify_credentials("admin", "k") is True


# --- omr-admin secret extraction (the wizard key transfer reads this) -------
def _proxy_with_config(tmp_path, payload) -> OmrProxy:
    cfg = tmp_path / "omr-admin-config.json"
    cfg.write_text(json.dumps(payload))
    proxy = OmrProxy()
    proxy.settings = SimpleNamespace(demo=False, omr_admin_config=str(cfg))
    return proxy


def test_tunnel_secrets_reads_real_config_shape(tmp_path):
    proxy = _proxy_with_config(tmp_path, {
        "port": 65500,
        "users": [{
            "openmptcprouter": {
                "user_password": "omr-pass",
                "shadowsocks_key": "ss-key",
                "glorytun_key": "gt-key",
                "v2ray_user": "uuid-1",
            },
            "admin": {"user_password": "admin-pass"},
        }],
    })
    secrets = asyncio.run(proxy.tunnel_secrets())
    assert secrets["user_password"] == "omr-pass"
    assert secrets["shadowsocks_key"] == "ss-key"
    assert secrets["glorytun_key"] == "gt-key"
    assert secrets["v2ray_user"] == "uuid-1"
    # The admin password must never leak into the router-bound secrets.
    assert "admin-pass" not in secrets.values()


def test_tunnel_secrets_omits_missing_fields(tmp_path):
    proxy = _proxy_with_config(tmp_path, {
        "users": [{"openmptcprouter": {"user_password": "p"}}]})
    secrets = asyncio.run(proxy.tunnel_secrets())
    assert secrets == {"user_password": "p"}


def test_tunnel_secrets_survives_missing_or_broken_config(tmp_path):
    proxy = OmrProxy()
    proxy.settings = SimpleNamespace(demo=False,
                                     omr_admin_config=str(tmp_path / "nope.json"))
    assert asyncio.run(proxy.tunnel_secrets()) == {}

    broken = tmp_path / "broken.json"
    broken.write_text("{not json")
    proxy.settings = SimpleNamespace(demo=False, omr_admin_config=str(broken))
    assert asyncio.run(proxy.tunnel_secrets()) == {}


def test_tunnel_secrets_handles_flat_user_layout(tmp_path):
    # Older configs keep the fields directly on users[0] instead of nesting
    # them under "openmptcprouter" — pick() must still find them.
    proxy = _proxy_with_config(tmp_path, {
        "users": [{"user_password": "flat-pass", "shadowsocks_key": "flat-ss"}]})
    secrets = asyncio.run(proxy.tunnel_secrets())
    assert secrets["user_password"] == "flat-pass"
    assert secrets["shadowsocks_key"] == "flat-ss"
