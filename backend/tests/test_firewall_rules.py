"""Real-mode tests for dashboard-managed Shorewall rules.

These deliberately run with ``demo=False`` against a temp rules file: the
previous rules implementation was a demo-only stub whose real-mode paths
returned empty/False while the UI reported success. Demo-mode tests could
never have caught that.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from schemas import FirewallRule, PortForward
from services.shorewall_service import ShorewallService


def _real_service(tmp_path):
    svc = ShorewallService()
    svc.settings = SimpleNamespace(demo=False)
    svc.path = str(tmp_path / "rules")
    svc.applied = 0

    def _fake_apply():
        svc.applied += 1

    svc._apply = _fake_apply  # never exec the shorewall binary in tests
    return svc


def _rule(**over) -> FirewallRule:
    base = dict(action="allow", src_zone="net", dest_zone="fw",
                proto="tcp", port="443", description="Web")
    base.update(over)
    return FirewallRule(**base)


# --- real-mode behaviour ----------------------------------------------------
def test_add_list_delete_roundtrip_on_disk(tmp_path):
    svc = _real_service(tmp_path)
    added = svc.add_rule(_rule(port="80,443", description="Web Server"))
    assert added.id
    assert svc.applied == 1

    rules = svc.list_rules()
    assert len(rules) == 1
    r = rules[0]
    assert (r.action, r.src_zone, r.dest_zone, r.proto, r.port) == \
        ("allow", "net", "fw", "tcp", "80,443")
    assert r.description == "Web Server"

    assert svc.delete_rule(added.id) is True
    assert svc.list_rules() == []
    assert svc.delete_rule("missing") is False


def test_rule_survives_as_shorewall_syntax(tmp_path):
    svc = _real_service(tmp_path)
    svc.add_rule(_rule(action="block", port="22", description="No SSH"))
    content = open(svc.path).read()
    # DROP line with $FW spelling and the metadata comment.
    assert "DROP\tnet\t$FW\ttcp\t22\t# id=" in content
    assert "desc=No_SSH" in content


def test_tcp_udp_rule_renders_two_lines_and_merges_back(tmp_path):
    svc = _real_service(tmp_path)
    svc.add_rule(_rule(proto="tcp/udp", port="27015"))
    lines = [l for l in open(svc.path).read().splitlines() if l.startswith("ACCEPT")]
    assert len(lines) == 2
    rules = svc.list_rules()
    assert len(rules) == 1
    assert rules[0].proto == "tcp/udp"


def test_disabled_rule_roundtrips(tmp_path):
    svc = _real_service(tmp_path)
    svc.add_rule(_rule(enabled=False))
    rules = svc.list_rules()
    assert len(rules) == 1 and rules[0].enabled is False


def test_foreign_lines_and_dnat_block_are_preserved(tmp_path):
    svc = _real_service(tmp_path)
    with open(svc.path, "w") as fh:
        fh.write("# OMR generated preamble\nACCEPT net $FW tcp 65500\n")

    svc.add_forward(PortForward(description="NAS", proto="tcp", src_port=8080,
                                dest_ip="192.168.100.10", dest_port=80, enabled=True))
    svc.add_rule(_rule())
    svc.add_rule(_rule(port="8443", description="Alt"))

    content = open(svc.path).read()
    # Hand-written lines outside the managed blocks stay untouched.
    assert "# OMR generated preamble" in content
    assert "ACCEPT net $FW tcp 65500" in content
    # Both managed blocks coexist and neither parser sees the other's lines.
    assert len(svc.list_forwards()) == 1
    assert len(svc.list_rules()) == 2
    # The foreign ACCEPT line (no id=) is not claimed by the dashboard.
    assert all(r.port != "65500" for r in svc.list_rules())


def test_delete_rewrites_only_the_rules_block(tmp_path):
    svc = _real_service(tmp_path)
    svc.add_forward(PortForward(description="NAS", proto="tcp", src_port=8080,
                                dest_ip="192.168.100.10", dest_port=80, enabled=True))
    keep = svc.add_rule(_rule())
    drop = svc.add_rule(_rule(port="8443"))
    assert svc.delete_rule(drop.id) is True
    assert [r.id for r in svc.list_rules()] == [keep.id]
    assert len(svc.list_forwards()) == 1


# --- forwards roundtrip fixes ----------------------------------------------
def test_tcp_udp_forward_parses_back_as_tcp_udp(tmp_path):
    svc = _real_service(tmp_path)
    svc.add_forward(PortForward(description="Game", proto="tcp/udp", src_port=27015,
                                dest_ip="192.168.100.20", dest_port=27015, enabled=True))
    forwards = svc.list_forwards()
    assert len(forwards) == 1
    assert forwards[0].proto == "tcp/udp"


def test_deny_cidrs_do_not_duplicate_for_tcp_udp(tmp_path):
    svc = _real_service(tmp_path)
    svc.add_forward(PortForward(description="X", proto="tcp/udp", src_port=9000,
                                dest_ip="192.168.100.30", dest_port=9000, enabled=True,
                                deny_src_cidrs=["198.51.100.0/24"]))
    forwards = svc.list_forwards()
    assert forwards[0].deny_src_cidrs == ["198.51.100.0/24"]


# --- input validation (the port lands verbatim in the rules file) -----------
@pytest.mark.parametrize("bad", [
    "", "80 443", "80;reboot", "80\nACCEPT net $FW tcp 22", "abc",
    "0", "70000", "5010:5000", "80,", "80,,443", "-1",
])
def test_port_expressions_that_could_break_the_file_are_rejected(bad):
    with pytest.raises(ValidationError):
        _rule(port=bad)


@pytest.mark.parametrize("ok", ["80", "80,443", "5000:5010", "25,587,993", "80,5000:5010"])
def test_legitimate_port_expressions_pass(ok):
    assert _rule(port=ok).port == ok


def test_unknown_zone_is_rejected():
    with pytest.raises(ValidationError):
        _rule(src_zone="net; DROP all")


def test_description_is_collapsed_to_one_line():
    r = _rule(description="line1\nline2\t tab")
    assert r.description == "line1 line2 tab"


def test_api_rejects_injection_port(client):
    res = client.post("/firewall/rules", json={
        "action": "allow", "src_zone": "net", "dest_zone": "fw",
        "proto": "tcp", "port": "80 443", "description": "x"})
    assert res.status_code == 422
