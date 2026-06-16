"""Read/write Shorewall rules for port forwarding (DNAT) and simple firewall.

Dashboard-managed rules live between sentinel markers in the rules file so we
never disturb the rest of the OMR-generated configuration:

    # >>> OMR-DASHBOARD MANAGED (do not edit by hand) >>>
    DNAT    net     loc:192.168.100.2:1194   udp     1194   -   -   -   # id=ab12 desc=OPNsense VPN
    # <<< OMR-DASHBOARD MANAGED <<<

Beyond the simple case, a rule can carry (R2 — see docs/routing-plan.de.md §3/§10):

  - a destination *port range* (``src_port``..``src_port_end``), rendered as
    Shorewall's native ``low:high`` DPORT syntax;
  - multiple weighted *targets* for load balancing, rendered as a comma list
    of ``ip:port`` in the DEST column (each target repeated by its weight —
    iptables' DNAT extension distributes connections evenly across a comma
    list natively, so weighting is approximated by repetition rather than
    needing a separate ``statistic`` match rule);
  - *source CIDR* allow-listing, rendered into the SOURCE column as
    ``net:cidr1,cidr2``, and deny-listing, rendered as separate ``DROP``
    lines placed before the DNAT line;
  - a *rate limit*, rendered into Shorewall's RATE LIMIT column (e.g.
    ``60/min``).

The simple single-target rules from before this extension keep rendering
exactly as before (additive, not replacing — see Leitprinzip 1 in the plan
doc), and old-format lines on disk still parse correctly.

In demo mode rules are kept in memory only.
"""
from __future__ import annotations

import logging
import os
import subprocess
import uuid
from typing import Optional

from config import get_settings
from schemas import FirewallRule, IngressTarget, PortForward

_BEGIN = "# >>> OMR-DASHBOARD MANAGED (do not edit by hand) >>>"
_END = "# <<< OMR-DASHBOARD MANAGED <<<"

_MAX_DEST_ENTRIES = 20  # cap on repeated dest:port entries when approximating weights

_log = logging.getLogger("omr_dashboard.shorewall")

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
        forwards: dict[str, PortForward] = {}
        order: list[str] = []
        deny_map: dict[str, list[str]] = {}
        in_block = False
        for line in self._read_lines():
            stripped = line.strip()
            if stripped == _BEGIN:
                in_block = True
                continue
            if stripped == _END:
                in_block = False
                continue
            if not in_block or not stripped or stripped.startswith("#"):
                continue
            action = stripped.split("#", 1)[0].split()[:1]
            if action and action[0].startswith("DROP"):
                fid, cidr = self._parse_deny_line(stripped)
                if fid:
                    deny_map.setdefault(fid, []).append(cidr)
                continue
            pf = self._parse_dnat_line(line)
            if pf and pf.id:
                if pf.id not in forwards:
                    order.append(pf.id)
                forwards[pf.id] = pf
            elif not pf:
                _log.warning(
                    "Überspringe unlesbare DNAT-Zeile im verwalteten Block: %r", line
                )
        result = []
        for fid in order:
            pf = forwards[fid]
            pf.deny_src_cidrs = deny_map.get(fid, [])
            result.append(pf)
        return result

    @staticmethod
    def _parse_deny_line(line: str) -> tuple[Optional[str], str]:
        # DROP    net:CIDR    loc:IP:PORT    proto    dport  -  -  -  # id=.. desc=..._deny
        try:
            code, comment = (line.split("#", 1) + [""])[:2]
            parts = code.split()
            source = parts[1]
            cidr = source.split(":", 1)[1] if source.startswith("net:") else source
            meta = dict(kv.split("=", 1) for kv in comment.strip().split() if "=" in kv)
            return meta.get("id"), cidr
        except (ValueError, IndexError):
            return None, ""

    @staticmethod
    def _parse_dnat_line(line: str) -> Optional[PortForward]:
        # DNAT[ -] source dest proto dport [sport origdest ratelimit]  # id=.. desc=..
        try:
            code, comment = (line.split("#", 1) + [""])[:2]
            parts = code.split()
            if not parts or not parts[0].startswith("DNAT"):
                return None
            enabled = not parts[0].endswith("-")
            source = parts[1]
            dest = parts[2]  # loc:IP:PORT or loc:IP1:PORT1,IP2:PORT2,...
            proto = parts[3]
            dport = parts[4]
            rate = parts[7] if len(parts) > 7 else "-"
            meta = dict(
                kv.split("=", 1) for kv in comment.strip().split() if "=" in kv
            )

            if ":" in dport:
                start_s, end_s = dport.split(":", 1)
                src_port, src_port_end = int(start_s), int(end_s)
            else:
                src_port, src_port_end = int(dport), None

            dest_body = dest.split(":", 1)[1] if dest.startswith("loc:") else dest
            seen: dict[tuple[str, int], int] = {}
            target_order: list[tuple[str, int]] = []
            for entry in dest_body.split(","):
                ip, port_s = entry.rsplit(":", 1)
                key = (ip, int(port_s))
                if key not in seen:
                    seen[key] = 0
                    target_order.append(key)
                seen[key] += 1
            dest_ip, dest_port = target_order[0]
            extra_targets = [
                IngressTarget(dest_ip=ip, dest_port=port, weight=min(seen[(ip, port)], 10))
                for ip, port in target_order[1:]
            ]

            allow_src_cidrs: list[str] = []
            if source.startswith("net:"):
                allow_src_cidrs = source.split(":", 1)[1].split(",")

            rate_limit_per_min = None
            if rate and rate != "-":
                rate_limit_per_min = int(rate.split("/", 1)[0])

            return PortForward(
                id=meta.get("id"),
                description=meta.get("desc", "").replace("_", " "),
                proto=proto,  # type: ignore[arg-type]
                src_port=src_port,
                src_port_end=src_port_end,
                dest_ip=dest_ip,
                dest_port=dest_port,
                enabled=enabled,
                extra_targets=extra_targets,
                allow_src_cidrs=allow_src_cidrs,
                rate_limit_per_min=rate_limit_per_min,
            )
        except (ValueError, IndexError):
            return None

    @staticmethod
    def _dport_token(pf: PortForward) -> str:
        if pf.src_port_end and pf.src_port_end > pf.src_port:
            return f"{pf.src_port}:{pf.src_port_end}"
        return str(pf.src_port)

    @staticmethod
    def _dest_token(pf: PortForward) -> str:
        targets: list[tuple[str, int, int]] = [(pf.dest_ip, pf.dest_port, 1)]
        targets += [(t.dest_ip, t.dest_port, t.weight) for t in pf.extra_targets]
        if len(targets) == 1:
            ip, port, _ = targets[0]
            return f"loc:{ip}:{port}"
        entries: list[str] = []
        for ip, port, weight in targets:
            entries.extend([f"{ip}:{port}"] * max(1, weight))
        return "loc:" + ",".join(entries[:_MAX_DEST_ENTRIES])

    @staticmethod
    def _source_token(pf: PortForward) -> str:
        if pf.allow_src_cidrs:
            return "net:" + ",".join(pf.allow_src_cidrs)
        return "net"

    def _render_forward(self, pf: PortForward) -> list[str]:
        prefix = "DNAT" if pf.enabled else "DNAT-"
        desc = (pf.description or "").replace(" ", "_")
        dport = self._dport_token(pf)
        lines = []
        for proto in _proto_tokens(pf.proto):
            for cidr in pf.deny_src_cidrs:
                lines.append(
                    f"DROP\tnet:{cidr}\tloc:{pf.dest_ip}:{pf.dest_port}\t{proto}\t{dport}"
                    f"\t-\t-\t-\t# id={pf.id} desc={desc}_deny"
                )
            rate = f"{pf.rate_limit_per_min}/min" if pf.rate_limit_per_min else "-"
            lines.append(
                f"{prefix}\t{self._source_token(pf)}\t{self._dest_token(pf)}\t{proto}\t{dport}"
                f"\t-\t-\t{rate}\t# id={pf.id} desc={desc}"
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
