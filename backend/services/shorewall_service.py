"""Read/write Shorewall rules for port forwarding (DNAT) and simple firewall.

Dashboard-managed rules live between sentinel markers in the rules file so we
never disturb the rest of the OMR-generated configuration:

    # >>> OMR-DASHBOARD MANAGED (do not edit by hand) >>>
    DNAT    net     loc:192.168.100.2:1194   udp     1194   # id=ab12 desc=OPNsense VPN
    # <<< OMR-DASHBOARD MANAGED <<<

In demo mode rules are kept in memory only.
"""
from __future__ import annotations

import os
import subprocess
import uuid
from typing import Optional

from config import get_settings
from schemas import FirewallRule, PortForward

_BEGIN = "# >>> OMR-DASHBOARD MANAGED (do not edit by hand) >>>"
_END = "# <<< OMR-DASHBOARD MANAGED <<<"

# In-memory store for demo mode.
_demo_forwards: list[PortForward] = [
    PortForward(id="demo1", description="NAS Web", proto="tcp", src_port=8080,
                dest_ip="192.168.100.10", dest_port=80, enabled=True),
    PortForward(id="demo2", description="OPNsense VPN", proto="udp", src_port=1194,
                dest_ip="192.168.100.2", dest_port=1194, enabled=True),
]
_demo_rules: list[FirewallRule] = []


def _proto_tokens(proto: str) -> list[str]:
    return ["tcp", "udp"] if proto == "tcp/udp" else [proto]


class ShorewallService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.path = self.settings.shorewall_rules

    # --- port forwarding ---------------------------------------------------
    def list_forwards(self) -> list[PortForward]:
        if self.settings.demo:
            return list(_demo_forwards)
        return self._parse_forwards()

    def add_forward(self, pf: PortForward) -> PortForward:
        pf.id = pf.id or uuid.uuid4().hex[:8]
        if self.settings.demo:
            _demo_forwards.append(pf)
            return pf
        forwards = self._parse_forwards()
        forwards.append(pf)
        self._write_forwards(forwards)
        self._apply()
        return pf

    def update_forward(self, pf_id: str, pf: PortForward) -> Optional[PortForward]:
        pf.id = pf_id
        if self.settings.demo:
            for i, existing in enumerate(_demo_forwards):
                if existing.id == pf_id:
                    _demo_forwards[i] = pf
                    return pf
            return None
        forwards = self._parse_forwards()
        found = False
        for i, existing in enumerate(forwards):
            if existing.id == pf_id:
                forwards[i] = pf
                found = True
        if not found:
            return None
        self._write_forwards(forwards)
        self._apply()
        return pf

    def delete_forward(self, pf_id: str) -> bool:
        if self.settings.demo:
            before = len(_demo_forwards)
            _demo_forwards[:] = [f for f in _demo_forwards if f.id != pf_id]
            return len(_demo_forwards) < before
        forwards = self._parse_forwards()
        new = [f for f in forwards if f.id != pf_id]
        if len(new) == len(forwards):
            return False
        self._write_forwards(new)
        self._apply()
        return True

    # --- parsing / writing -------------------------------------------------
    def _read_lines(self) -> list[str]:
        if not os.path.exists(self.path):
            return []
        with open(self.path) as fh:
            return fh.read().splitlines()

    def _parse_forwards(self) -> list[PortForward]:
        forwards: list[PortForward] = []
        in_block = False
        for line in self._read_lines():
            if line.strip() == _BEGIN:
                in_block = True
                continue
            if line.strip() == _END:
                in_block = False
                continue
            if not in_block or not line.strip() or line.strip().startswith("#"):
                continue
            pf = self._parse_dnat_line(line)
            if pf:
                forwards.append(pf)
        return forwards

    @staticmethod
    def _parse_dnat_line(line: str) -> Optional[PortForward]:
        # DNAT[ -] net loc:IP:PORT proto src_port  # id=.. desc=..
        try:
            code, comment = (line.split("#", 1) + [""])[:2]
            parts = code.split()
            if not parts or not parts[0].startswith("DNAT"):
                return None
            enabled = not parts[0].endswith("-")
            dest = parts[2]  # loc:IP:PORT
            _, dest_ip, dest_port = dest.split(":")
            proto = parts[3]
            src_port = int(parts[4])
            meta = dict(
                kv.split("=", 1) for kv in comment.strip().split() if "=" in kv
            )
            return PortForward(
                id=meta.get("id"),
                description=meta.get("desc", "").replace("_", " "),
                proto=proto,  # type: ignore[arg-type]
                src_port=src_port,
                dest_ip=dest_ip,
                dest_port=int(dest_port),
                enabled=enabled,
            )
        except (ValueError, IndexError):
            return None

    def _render_forward(self, pf: PortForward) -> list[str]:
        prefix = "DNAT" if pf.enabled else "DNAT-"
        desc = (pf.description or "").replace(" ", "_")
        lines = []
        for proto in _proto_tokens(pf.proto):
            lines.append(
                f"{prefix}\tnet\tloc:{pf.dest_ip}:{pf.dest_port}\t{proto}\t{pf.src_port}"
                f"\t# id={pf.id} desc={desc}"
            )
        return lines

    def _write_forwards(self, forwards: list[PortForward]) -> None:
        lines = self._read_lines()
        # strip existing managed block
        out: list[str] = []
        in_block = False
        for line in lines:
            if line.strip() == _BEGIN:
                in_block = True
                continue
            if line.strip() == _END:
                in_block = False
                continue
            if not in_block:
                out.append(line)
        # append fresh managed block
        out.append(_BEGIN)
        for pf in forwards:
            out.extend(self._render_forward(pf))
        out.append(_END)
        with open(self.path, "w") as fh:
            fh.write("\n".join(out) + "\n")

    def _apply(self) -> None:
        try:
            subprocess.run(["shorewall", "restart"], check=False, capture_output=True, timeout=60)
        except (FileNotFoundError, subprocess.SubprocessError):
            pass

    # --- firewall rules (simple) ------------------------------------------
    def list_rules(self) -> list[FirewallRule]:
        if self.settings.demo:
            return list(_demo_rules)
        # For now we surface only dashboard-managed accept rules; full parsing
        # of arbitrary shorewall rules is intentionally out of scope.
        return []

    def add_rule(self, rule: FirewallRule) -> FirewallRule:
        rule.id = rule.id or uuid.uuid4().hex[:8]
        if self.settings.demo:
            _demo_rules.append(rule)
        return rule

    def delete_rule(self, rule_id: str) -> bool:
        if self.settings.demo:
            before = len(_demo_rules)
            _demo_rules[:] = [r for r in _demo_rules if r.id != rule_id]
            return len(_demo_rules) < before
        return False


# Common firewall presets surfaced in the UI.
FIREWALL_PRESETS = [
    {"id": "web", "name": "Web-Server", "ports": "80,443", "proto": "tcp",
     "description": "HTTP und HTTPS von außen erreichbar"},
    {"id": "mail", "name": "Mail-Server", "ports": "25,587,993", "proto": "tcp",
     "description": "SMTP, Submission und IMAPS"},
    {"id": "game", "name": "Game-Server", "ports": "27015,25565", "proto": "tcp/udp",
     "description": "Häufige Gaming-Ports (anpassbar)"},
    {"id": "ssh", "name": "SSH-Zugang", "ports": "22", "proto": "tcp",
     "description": "SSH (mit Rate-Limit empfohlen)"},
]
