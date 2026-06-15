"""Client for the router's LuCI ubus JSON-RPC endpoint.

Used to detect WAN interfaces, read live per-link state, push configuration
(VPS IP, tunnel keys, protocol) during the wizard, and read board/version info.
Authentication follows LuCI's ``session.login`` flow; the session token is
cached and refreshed on expiry. In demo mode all calls return synthetic data.
"""
from __future__ import annotations

from typing import Any, Optional

import httpx

from config import get_settings
from schemas import LinkType, WizardWan


def infer_type(interface: str, name: str = "") -> LinkType:
    """Best-effort WAN type detection from interface/name conventions."""
    s = f"{interface} {name}".lower()
    if any(k in s for k in ("wwan", "lte", "4g", "modem", "usb")):
        return LinkType.lte
    if "5g" in s:
        return LinkType.fiveg
    if any(k in s for k in ("sat", "starlink")):
        return LinkType.satellite
    # Fiber is the more specific positive signal, so it wins over a generic
    # "dsl" substring (e.g. a link labelled "Fiber DSL").
    if any(k in s for k in ("fiber", "fibre", "ftth", "sfp")):
        return LinkType.fiber
    if any(k in s for k in ("ppp", "dsl", "vdsl", "adsl")):
        return LinkType.dsl
    if interface.startswith("eth") or "lan" in s:
        return LinkType.ethernet
    return LinkType.other


class RouterProxy:
    def __init__(
        self,
        ip: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
    ) -> None:
        self.settings = get_settings()
        self.ip = ip or self.settings.router_ip
        self.user = user or self.settings.router_user
        self.password = password if password is not None else self.settings.router_pass
        self._session: Optional[str] = None

    @property
    def _url(self) -> str:
        return f"http://{self.ip}/ubus"

    # --- low level ---------------------------------------------------------
    async def _login(self) -> Optional[str]:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "call",
            "params": [
                "00000000000000000000000000000000",
                "session",
                "login",
                {"username": self.user, "password": self.password},
            ],
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(self._url, json=payload)
                data = resp.json()
                return data["result"][1]["ubus_rpc_session"]
        except Exception:
            return None

    async def _call(self, obj: str, method: str, params: dict | None = None) -> Optional[Any]:
        if self._session is None:
            self._session = await self._login()
        if self._session is None:
            return None
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "call",
            "params": [self._session, obj, method, params or {}],
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(self._url, json=payload)
                data = resp.json()
                result = data.get("result")
                if not result:
                    return None
                # result == [code, payload]; code 0 == ok
                if result[0] != 0:
                    # session likely expired; retry once
                    self._session = await self._login()
                    return None
                return result[1] if len(result) > 1 else {}
        except Exception:
            return None

    # --- high level --------------------------------------------------------
    async def ping(self) -> bool:
        if self.settings.demo:
            return True
        return await self._login() is not None

    async def board(self) -> dict:
        if self.settings.demo:
            return {"release": {"version": "23.05.3"}, "kernel": "6.1.90"}
        return await self._call("system", "board") or {}

    async def detect_wans(self) -> list[WizardWan]:
        if self.settings.demo:
            return [
                WizardWan(id="wan", interface="eth0.2", detected_type=LinkType.fiber,
                          label="Fiber DSL", ip="203.0.113.5", up=True),
                WizardWan(id="wan2", interface="wwan0", detected_type=LinkType.lte,
                          label="LTE Telekom", ip="10.128.2.1", up=True),
                WizardWan(id="wan3", interface="wwan1", detected_type=LinkType.fiveg,
                          label="5G Vodafone", ip="10.64.9.3", up=True),
            ]
        dump = await self._call("network.interface", "dump") or {}
        wans: list[WizardWan] = []
        for iface in dump.get("interface", []):
            name = iface.get("interface", "")
            if not name.startswith("wan") and "wan" not in name.lower():
                continue
            l3 = iface.get("l3_device") or iface.get("device", "")
            ipv4 = iface.get("ipv4-address") or []
            ip = ipv4[0]["address"] if ipv4 else None
            wans.append(
                WizardWan(
                    id=name,
                    interface=l3,
                    detected_type=infer_type(l3, name),
                    label=name.upper(),
                    ip=ip,
                    up=bool(iface.get("up")),
                )
            )
        return wans

    async def uci_set(self, config: str, section: str, values: dict) -> bool:
        if self.settings.demo:
            return True
        res = await self._call("uci", "set", {"config": config, "section": section, "values": values})
        return res is not None

    async def uci_commit(self, config: str) -> bool:
        if self.settings.demo:
            return True
        res = await self._call("uci", "commit", {"config": config})
        return res is not None

    async def exec_ping(self, target: str, count: int = 5) -> str:
        """Run ping on the router via the file.exec ubus method."""
        if self.settings.demo:
            return (
                f"PING {target}: avg 18.4 ms, 0% loss (demo)\n"
                "rtt min/avg/max = 14.1/18.4/24.0 ms"
            )
        res = await self._call("file", "exec", {"command": "ping", "params": ["-c", str(count), target]})
        if isinstance(res, dict):
            return res.get("stdout", "")
        return ""
