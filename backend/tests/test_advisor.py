"""Tests for the configuration advisor.

Each check is exercised in isolation: a finding must appear exactly when the
condition holds, and must stay silent otherwise — a system check that cries
wolf gets ignored, which is worse than not having one.
"""
from __future__ import annotations

from types import SimpleNamespace

from schemas import BondState, DashboardStatus, LinkState, LinkStatus, LinkType, TunnelStatus
from services import advisor


def _settings(**over):
    base = dict(demo=False, jwt_secret="a-real-secret", dashboard_pass="pw",
                omr_admin_key="key", router_pass="rpw")
    base.update(over)
    return SimpleNamespace(**base)


def _link(link_id="wan", label="WAN", type=LinkType.fiber, enabled=True,
          state=LinkState.up, loss=0.0, latency=10.0):
    return LinkStatus(id=link_id, label=label, type=type, enabled=enabled,
                      state=state, packet_loss_pct=loss, latency_ms=latency)


def _ctx(links=None, state=BondState.bonded, protocol="glorytun_tcp", **over):
    status = DashboardStatus(
        state=state,
        links=links if links is not None else [_link(), _link("wan2", "WAN2")],
        tunnel=TunnelStatus(protocol=protocol, up=state != BondState.offline),
    )
    kwargs = dict(settings=_settings(), status=status, quotas={}, usage={},
                  alerts={"telegram_enabled": True, "cooldown_minutes": 10},
                  bind_addr="10.255.247.1", month_progress=1.0)
    kwargs.update(over)
    return advisor.AdvisorContext(**kwargs)


def _ids(findings):
    return {f.id for f in findings}


# --- security ---------------------------------------------------------------
def test_default_jwt_secret_is_an_error():
    ctx = _ctx(settings=_settings(jwt_secret=advisor.DEFAULT_JWT_SECRET))
    f = advisor.check_jwt_secret(ctx)
    assert len(f) == 1 and f[0].severity == "error"
    assert f[0].page == "/system"


def test_jwt_check_is_silent_in_demo():
    ctx = _ctx(settings=_settings(demo=True, jwt_secret=advisor.DEFAULT_JWT_SECRET))
    assert advisor.check_jwt_secret(ctx) == []


def test_missing_password_warns_only_when_truly_unset():
    assert advisor.check_dashboard_password(_ctx()) == []
    ctx = _ctx(settings=_settings(dashboard_pass="", omr_admin_key=""))
    assert len(advisor.check_dashboard_password(ctx)) == 1


def test_public_bind_address_is_flagged():
    assert advisor.check_bind_address(_ctx(bind_addr="0.0.0.0"))[0].severity == "error"
    assert advisor.check_bind_address(_ctx(bind_addr="::"))[0].severity == "error"
    # A routable address — the case that actually exposes the dashboard.
    assert advisor.check_bind_address(_ctx(bind_addr="93.184.216.34"))[0].severity == "error"


def test_private_and_loopback_bind_addresses_are_fine():
    # Note: Python classifies the RFC 5737 documentation ranges (203.0.113.0/24,
    # 198.51.100.0/24, 192.0.2.0/24) as private, so they land here too.
    for addr in ("127.0.0.1", "10.255.247.1", "192.168.1.5", "172.16.0.9", "203.0.113.9"):
        assert advisor.check_bind_address(_ctx(bind_addr=addr)) == [], addr


def test_hostname_bind_address_does_not_cry_wolf():
    # Not resolvable to a judgement — staying quiet beats a false alarm.
    assert advisor.check_bind_address(_ctx(bind_addr="dashboard.internal")) == []


def test_missing_router_password_warns():
    assert advisor.check_router_credentials(_ctx()) == []
    ctx = _ctx(settings=_settings(router_pass=""))
    assert advisor.check_router_credentials(ctx)[0].severity == "warn"


# --- connectivity -----------------------------------------------------------
def test_offline_bond_is_an_error():
    assert advisor.check_tunnel(_ctx(state=BondState.offline))[0].severity == "error"
    assert advisor.check_tunnel(_ctx()) == []


def test_single_link_is_informational_not_an_error():
    ctx = _ctx(links=[_link()])
    f = advisor.check_link_count(ctx)
    # One link is a legitimate setup, just not bonding — must not be alarming.
    assert len(f) == 1 and f[0].severity == "info"
    assert advisor.check_link_count(_ctx()) == []


def test_poor_link_is_reported_with_its_numbers():
    ctx = _ctx(links=[_link(loss=5.0), _link("wan2", "WAN2")])
    f = advisor.check_poor_links(ctx)
    assert len(f) == 1
    assert "5.0 % Paketverlust" in f[0].detail

    ctx = _ctx(links=[_link(latency=400.0)])
    assert "400 ms Latenz" in advisor.check_poor_links(ctx)[0].detail


def test_down_and_disabled_links_are_not_reported_as_poor():
    # A link that is down is already covered by the bond state; repeating it
    # here would just add noise.
    ctx = _ctx(links=[_link(state=LinkState.down, loss=99.0),
                      _link("w2", "W2", enabled=False, loss=99.0)])
    assert advisor.check_poor_links(ctx) == []


# --- usage ------------------------------------------------------------------
def test_metered_link_without_cap_warns_and_suggests_a_value():
    ctx = _ctx(links=[_link("wan2", "LTE", type=LinkType.lte)])
    f = advisor.check_metered_without_cap(ctx)
    assert len(f) == 1 and f[0].severity == "warn"
    assert "GB" in f[0].action and f[0].page == "/usage"


def test_wired_link_without_cap_is_not_flagged():
    assert advisor.check_metered_without_cap(_ctx()) == []


def test_metered_link_with_cap_is_not_flagged():
    ctx = _ctx(links=[_link("wan2", "LTE", type=LinkType.lte)],
               quotas={"wan2": {"cap_gb": 50, "warn_pct": 80}})
    assert advisor.check_metered_without_cap(ctx) == []


def test_quota_thresholds_escalate():
    links = [_link("wan2", "LTE", type=LinkType.lte)]
    quotas = {"wan2": {"cap_gb": 10, "warn_pct": 80}}
    # 85% -> warn
    ctx = _ctx(links=links, quotas=quotas, usage={"wan2": (8.5e9, 0.0)})
    assert advisor.check_quota_status(ctx)[0].severity == "warn"
    # 100% -> error
    ctx = _ctx(links=links, quotas=quotas, usage={"wan2": (10e9, 0.5e9)})
    assert advisor.check_quota_status(ctx)[0].severity == "error"
    # below threshold, and on track -> silent
    ctx = _ctx(links=links, quotas=quotas, usage={"wan2": (1e9, 0.0)},
               month_progress=0.5)
    assert advisor.check_quota_status(ctx) == []


def test_projection_warns_before_the_cap_is_hit():
    links = [_link("wan2", "LTE", type=LinkType.lte)]
    quotas = {"wan2": {"cap_gb": 10, "warn_pct": 80}}
    # Half the month gone, 60% used -> on track for ~120%, still under the
    # warn threshold, so only the forecast can catch this.
    ctx = _ctx(links=links, quotas=quotas, usage={"wan2": (6e9, 0.0)},
               month_progress=0.5)
    f = advisor.check_quota_status(ctx)
    assert len(f) == 1
    assert f[0].id == "cap_forecast_wan2"
    assert f[0].severity == "info"      # a forecast is not yet a problem
    assert "120 %" in f[0].detail


def test_projection_stays_quiet_early_in_the_month():
    # Two days in, one big download must not "predict" a blown cap.
    links = [_link("wan2", "LTE", type=LinkType.lte)]
    ctx = _ctx(links=links, quotas={"wan2": {"cap_gb": 10, "warn_pct": 80}},
               usage={"wan2": (2e9, 0.0)}, month_progress=0.05)
    assert advisor.check_quota_status(ctx) == []


def test_projection_silent_when_on_track():
    links = [_link("wan2", "LTE", type=LinkType.lte)]
    ctx = _ctx(links=links, quotas={"wan2": {"cap_gb": 10, "warn_pct": 80}},
               usage={"wan2": (3e9, 0.0)}, month_progress=0.5)   # ~60% projected
    assert advisor.check_quota_status(ctx) == []


# --- alerting ---------------------------------------------------------------
def test_no_alert_channel_is_informational():
    ctx = _ctx(alerts={})
    f = advisor.check_alert_channels(ctx)
    assert len(f) == 1 and f[0].severity == "info"
    assert advisor.check_alert_channels(_ctx()) == []


def test_cooldown_hint_only_applies_when_a_channel_is_on():
    assert advisor.check_alert_cooldown(_ctx(alerts={"cooldown_minutes": 0})) == []
    ctx = _ctx(alerts={"telegram_enabled": True, "cooldown_minutes": 0})
    assert advisor.check_alert_cooldown(ctx)[0].severity == "info"


# --- protocol recommendation ------------------------------------------------
def test_recommendation_follows_link_mix():
    mobile = [_link("a", "LTE", type=LinkType.lte), _link("b", "5G", type=LinkType.fiveg)]
    assert advisor.recommend_protocol(mobile)[0] == "glorytun_udp"
    wired = [_link("a", "Fiber", type=LinkType.fiber), _link("b", "DSL", type=LinkType.dsl)]
    assert advisor.recommend_protocol(wired)[0] == "glorytun_tcp"


def test_recommendation_handles_no_links():
    proto, reason = advisor.recommend_protocol([])
    assert proto == "glorytun_tcp" and reason


def test_protocol_suggestion_is_silent_when_already_optimal():
    ctx = _ctx(protocol="glorytun_tcp")   # wired links -> tcp is the pick
    assert advisor.check_protocol_choice(ctx) == []
    ctx = _ctx(links=[_link("a", "LTE", type=LinkType.lte)], protocol="glorytun_tcp")
    assert advisor.check_protocol_choice(ctx)[0].severity == "info"


# --- runner -----------------------------------------------------------------
def test_healthy_setup_produces_no_findings():
    assert advisor.evaluate(_ctx()) == []


def test_findings_are_sorted_most_severe_first():
    ctx = _ctx(state=BondState.offline, alerts={},
               settings=_settings(jwt_secret=advisor.DEFAULT_JWT_SECRET),
               links=[_link("wan2", "LTE", type=LinkType.lte)])
    severities = [f.severity for f in advisor.evaluate(ctx)]
    assert severities == sorted(severities, key=lambda s: {"error": 0, "warn": 1, "info": 2}[s])
    assert "tunnel_offline" in _ids(advisor.evaluate(ctx))


def test_one_broken_check_does_not_lose_the_others(monkeypatch):
    def boom(_ctx):
        raise RuntimeError("check exploded")

    monkeypatch.setattr(advisor, "CHECKS", [boom, advisor.check_tunnel])
    findings = advisor.evaluate(_ctx(state=BondState.offline))
    assert _ids(findings) == {"tunnel_offline"}


def test_endpoint_reports_counts(client):
    body = client.get("/health-check").json()
    assert body["checked"] == len(advisor.CHECKS)
    assert body["errors"] + body["warnings"] + body["infos"] == len(body["findings"])
