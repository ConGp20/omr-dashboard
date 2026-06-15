"""Diagnostics: ping (router + VPS), traceroute, speedtest, MTU finder."""
from __future__ import annotations

import asyncio
import random
import re
import subprocess

from fastapi import APIRouter, Depends

from auth import require_user
from config import get_settings
from deps import get_store
from schemas import PingRequest, PingResult
from services.router_proxy import RouterProxy

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


def _parse_ping(raw: str, source: str, target: str) -> PingResult:
    result = PingResult(source=source, target=target, raw=raw)
    loss = re.search(r"(\d+(?:\.\d+)?)% packet loss", raw)
    if loss:
        result.loss_pct = float(loss.group(1))
    stats = re.search(r"=\s*([\d.]+)/([\d.]+)/([\d.]+)", raw)
    if stats:
        result.min_ms = float(stats.group(1))
        result.avg_ms = float(stats.group(2))
        result.max_ms = float(stats.group(3))
    return result


async def _vps_ping(target: str, count: int) -> str:
    if get_settings().demo:
        avg = random.uniform(10, 40)
        return (f"PING {target}\n--- {target} ping statistics ---\n"
                f"{count} packets transmitted, {count} received, 0% packet loss\n"
                f"rtt min/avg/max = {avg-3:.1f}/{avg:.1f}/{avg+5:.1f} ms")
    try:
        proc = await asyncio.create_subprocess_exec(
            "ping", "-c", str(count), target,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out, _ = await proc.communicate()
        return out.decode(errors="ignore")
    except (FileNotFoundError, OSError):
        return ""


@router.post("/ping", response_model=list[PingResult])
async def ping(req: PingRequest, _: str = Depends(require_user)) -> list[PingResult]:
    router_raw, vps_raw = await asyncio.gather(
        RouterProxy().exec_ping(req.target, req.count),
        _vps_ping(req.target, req.count),
    )
    return [
        _parse_ping(router_raw, "router", req.target),
        _parse_ping(vps_raw, "vps", req.target),
    ]


@router.post("/speedtest")
async def speedtest(_: str = Depends(require_user)) -> dict:
    """Run an aggregated speed test (uses omr-test-speed on the VPS)."""
    settings = get_settings()
    if settings.demo:
        rx = round(random.uniform(80, 160), 1)
        tx = round(random.uniform(20, 45), 1)
        await get_store().add_speedtest("aggregated", None, rx, tx, "demo-server")
        return {"download_mbps": rx, "upload_mbps": tx, "server": "demo-server"}
    try:
        proc = await asyncio.create_subprocess_exec(
            "/omr-test-speed", stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out, _ = await proc.communicate()
        text = out.decode(errors="ignore")
        rx = _extract_mbps(text, "download") or 0.0
        tx = _extract_mbps(text, "upload") or 0.0
        await get_store().add_speedtest("aggregated", None, rx, tx, "omr")
        return {"download_mbps": rx, "upload_mbps": tx, "raw": text}
    except (FileNotFoundError, OSError):
        return {"download_mbps": 0, "upload_mbps": 0, "error": "omr-test-speed nicht verfügbar"}


def _extract_mbps(text: str, kind: str) -> float | None:
    m = re.search(rf"{kind}[^\d]*([\d.]+)\s*Mbits?/sec", text, re.IGNORECASE)
    return float(m.group(1)) if m else None


@router.get("/speedtest/history")
async def speedtest_history(_: str = Depends(require_user)) -> dict:
    return {"results": await get_store().speedtests(limit=20)}


@router.post("/mtu")
async def mtu_finder(_: str = Depends(require_user)) -> dict:
    """Suggest an optimal MTU per WAN (demo returns typical values)."""
    if get_settings().demo:
        return {"results": [
            {"link": "wan", "mtu": 1492, "note": "PPPoE-typisch"},
            {"link": "wan2", "mtu": 1428, "note": "LTE-typisch"},
            {"link": "wan3", "mtu": 1440, "note": "5G-typisch"},
        ]}
    return {"results": [], "note": "MTU-Ermittlung erfordert aktive WAN-Links"}
