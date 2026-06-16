"""Proxy to the existing OMR Admin FastAPI service (port 65500).

The existing API (``omr-admin.py``, maintained upstream) is the source of truth
for tunnel status and protocol switching. This module translates its responses
into the normalized dashboard schemas. In demo mode it returns synthetic data.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Optional

import httpx

from config import get_settings
from schemas import BondState, DashboardStatus, ProtocolInfo, TunnelStatus
from services import demo_data

# Plain-language metadata for each protocol the VPS can run.
PROTOCOL_META: dict[str, dict[str, Any]] = {
    "glorytun_tcp": {
        "name": "Glorytun TCP",
        "good_for": "Stabile Leitungen mit konstantem Durchsatz (Fiber, VDSL). Geringer Overhead.",
        "avoid_when": "Der ISP betreibt Deep Packet Inspection oder drosselt unbekannte Protokolle.",
        "technical": "Eigenes Protokoll über TCP, MPTCP-optimiert, ChaCha20-Poly1305.",
        "vps_port": 65001,
    },
    "glorytun_udp": {
        "name": "Glorytun UDP",
        "good_for": "Leitungen mit schwankender Latenz (LTE/5G). Niedrige Latenz.",
        "avoid_when": "UDP ist im Netz stark eingeschränkt oder blockiert.",
        "technical": "Glorytun über UDP mit Multipath-Unterstützung, ChaCha20-Poly1305.",
        "vps_port": 65001,
    },
    "shadowsocks": {
        "name": "Shadowsocks",
        "good_for": "Netze mit Deep Packet Inspection oder aggressivem Traffic-Shaping.",
        "avoid_when": "Maximale Rohleistung ohne Verschleierungs-Overhead gefragt ist.",
        "technical": "SOCKS5-Proxy mit Verschlüsselung, MPTCP, optional obfs.",
        "vps_port": 65101,
    },
    "wireguard": {
        "name": "WireGuard",
        "good_for": "Firmennetze, statische IPs, niedrige Latenz, moderner Stack.",
        "avoid_when": "Viele mobile WANs mit häufigem Adresswechsel im Einsatz sind.",
        "technical": "WireGuard-Tunnel, Curve25519 + ChaCha20-Poly1305.",
        "vps_port": 65311,
    },
    "mlvpn": {
        "name": "MLVPN",
        "good_for": "Maximale Link-Aggregation ohne Abhängigkeit vom MPTCP-Kernel.",
        "avoid_when": "Sehr niedrige Latenz wichtiger ist als reine Aggregation.",
        "technical": "Dediziertes Multi-Link-VPN, aggregiert auf Paketebene.",
        "vps_port": 65201,
    },
    "openvpn": {
        "name": "OpenVPN",
        "good_for": "Kompatibilität mit bestehender OpenVPN-Infrastruktur.",
        "avoid_when": "Beste Leistung oder moderner Stack im Vordergrund stehen.",
        "technical": "OpenVPN, optional Bonding über mehrere Instanzen.",
        "vps_port": 65301,
    },
}


class OmrProxy:
    def __init__(self) -> None:
        self.settings = get_settings()

    # --- low level ---------------------------------------------------------
    def _client(self) -> httpx.AsyncClient:
        # The omr-admin cert is self-signed; we talk to it over loopback.
        headers = {}
        if self.settings.omr_admin_key:
            headers["Authorization"] = f"Bearer {self.settings.omr_admin_key}"
        return httpx.AsyncClient(
            base_url=self.settings.omr_admin_url,
            headers=headers,
            verify=False,
            timeout=15.0,
        )

    async def _get(self, path: str) -> Optional[dict]:
        try:
            async with self._client() as client:
                resp = await client.get(path)
                resp.raise_for_status()
                return resp.json()
        except Exception:
            return None

    async def _post(self, path: str, payload: dict) -> Optional[dict]:
        try:
            async with self._client() as client:
                resp = await client.post(path, json=payload)
                resp.raise_for_status()
                return resp.json() if resp.content else {}
        except Exception:
            return None

    # --- high level --------------------------------------------------------
    async def ping(self) -> bool:
        if self.settings.demo:
            return True
        return await self._get("/") is not None

    def current_vpn(self) -> str:
        """Read the active protocol from the VPS state file."""
        if self.settings.demo:
            return "glorytun_tcp"
        path = Path(self.settings.omr_admin_config).parent / "current-vpn"
        try:
            return path.read_text().strip()
        except OSError:
            return "glorytun_tcp"

    async def status(self) -> DashboardStatus:
        if self.settings.demo:
            return demo_data.dashboard_status()
        # Real mode: combine omr-admin status with whatever it reports. The
        # router_proxy enriches per-link metrics; here we provide tunnel state.
        raw = await self._get("/status") or {}
        # The shape of /status varies by omr-admin version; we defensively map.
        return self._map_status(raw)

    def _map_status(self, raw: dict) -> DashboardStatus:
        # Minimal mapping; router_proxy fills in link details in the aggregator.
        vpn = self.current_vpn()
        up = bool(raw)
        tunnel = TunnelStatus(protocol=vpn, up=up)
        config_path = Path(self.settings.omr_admin_config).parent / "current-vpn"
        return DashboardStatus(
            configured=config_path.exists(),
            state=BondState.bonded if up else BondState.offline,
            tunnel=tunnel,
            vps_public_ip=raw.get("public_ip") if isinstance(raw, dict) else None,
            timestamp=time.time(),
        )

    async def protocols(self) -> list[ProtocolInfo]:
        active = self.current_vpn()
        available = await self._available_protocols()
        out: list[ProtocolInfo] = []
        for pid, meta in PROTOCOL_META.items():
            out.append(
                ProtocolInfo(
                    id=pid,
                    name=meta["name"],
                    active=(pid == active),
                    available=(pid in available) if available else True,
                    good_for=meta["good_for"],
                    avoid_when=meta["avoid_when"],
                    technical=meta["technical"],
                    vps_port=meta.get("vps_port"),
                )
            )
        return out

    async def _available_protocols(self) -> list[str]:
        if self.settings.demo:
            return ["glorytun_tcp", "glorytun_udp", "shadowsocks", "wireguard", "mlvpn", "openvpn"]
        # Probe which systemd units exist via omr-admin if it exposes them,
        # otherwise assume all are available.
        data = await self._get("/")
        if isinstance(data, dict) and "vpn" in data:
            return list(data["vpn"])
        return list(PROTOCOL_META.keys())

    async def switch_protocol(self, protocol: str) -> bool:
        if self.settings.demo:
            return True
        result = await self._post("/vpn", {"vpn": protocol})
        return result is not None

    def read_admin_config(self) -> dict:
        if self.settings.demo:
            return {"port": 65500, "users": [{"openmptcprouter": {}, "admin": {}}]}
        try:
            with open(self.settings.omr_admin_config) as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError):
            return {}
