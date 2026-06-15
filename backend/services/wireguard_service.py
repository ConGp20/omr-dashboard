"""Manage an optional WireGuard 'exit node' on the VPS.

When enabled, traffic leaving the VPS is routed through an upstream WireGuard
peer (e.g. a privacy VPN or a second server) instead of exiting directly. The
config is persisted as JSON under the data dir; applying it writes a wg-quick
interface and a policy route. In demo mode everything is in-memory.
"""
from __future__ import annotations

import json
import os
import subprocess
from typing import Optional

from config import get_settings
from schemas import ExitVpn

_WG_IFACE = "omr-exit"


class WireguardService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._path = os.path.join(self.settings.data_dir, "exit-vpn.json")
        os.makedirs(self.settings.data_dir, exist_ok=True)

    def get_exit_vpn(self) -> ExitVpn:
        if not os.path.exists(self._path):
            return ExitVpn()
        try:
            with open(self._path) as fh:
                data = json.load(fh)
            # Never echo the private key back to clients.
            data.pop("private_key", None)
            return ExitVpn(**data)
        except (OSError, json.JSONDecodeError, TypeError):
            return ExitVpn()

    def set_exit_vpn(self, config: ExitVpn) -> tuple["ExitVpn", str]:
        # Preserve a previously stored private key if the client didn't resend it.
        if not config.private_key and os.path.exists(self._path):
            try:
                with open(self._path) as fh:
                    config.private_key = json.load(fh).get("private_key")
            except (OSError, json.JSONDecodeError):
                pass
        with open(self._path, "w") as fh:
            json.dump(config.model_dump(), fh)
        warning = ""
        if not self.settings.demo:
            warning = self._apply(config)
        result = config.model_copy()
        result.private_key = None
        return result, warning

    def _apply(self, config: ExitVpn) -> str:
        """Apply the WireGuard config. Returns a warning string on non-fatal failure."""
        try:
            if not config.enabled or config.type != "wireguard":
                subprocess.run(["wg-quick", "down", _WG_IFACE], check=False,
                               capture_output=True, timeout=30)
                return ""
            conf = self._render_wg_conf(config)
            conf_path = f"/etc/wireguard/{_WG_IFACE}.conf"
            os.makedirs("/etc/wireguard", exist_ok=True)
            with open(conf_path, "w") as fh:
                fh.write(conf)
            os.chmod(conf_path, 0o600)
            subprocess.run(["wg-quick", "down", _WG_IFACE], check=False,
                           capture_output=True, timeout=30)
            r = subprocess.run(["wg-quick", "up", _WG_IFACE], check=False,
                               capture_output=True, timeout=30)
            if r.returncode != 0:
                return r.stderr.decode(errors="replace").strip() or "wg-quick up fehlgeschlagen"
            return ""
        except FileNotFoundError:
            return "wg-quick nicht gefunden — WireGuard ist nicht installiert"
        except (subprocess.SubprocessError, OSError) as exc:
            return str(exc)

    def _render_wg_conf(self, config: ExitVpn) -> str:
        lines = [
            "[Interface]",
            f"PrivateKey = {config.private_key or ''}",
        ]
        if config.kill_switch:
            lines.append("PostUp = iptables -I OUTPUT ! -o %i -m mark ! --mark $(wg show %i fwmark) -m addrtype ! --dst-type LOCAL -j REJECT")
            lines.append("PreDown = iptables -D OUTPUT ! -o %i -m mark ! --mark $(wg show %i fwmark) -m addrtype ! --dst-type LOCAL -j REJECT")
        lines += [
            "",
            "[Peer]",
            f"PublicKey = {config.public_key or ''}",
            f"Endpoint = {config.endpoint or ''}",
            f"AllowedIPs = {config.allowed_ips}",
            "PersistentKeepalive = 25",
        ]
        return "\n".join(lines) + "\n"
