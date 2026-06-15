"""DNS configuration (upstream resolvers + local entries)."""
from __future__ import annotations

import json
import os

from fastapi import APIRouter, Depends

from auth import require_user
from config import get_settings
from schemas import DnsConfig

router = APIRouter(prefix="/dns", tags=["dns"])

DOH_PROVIDERS = {
    "cloudflare": "https://cloudflare-dns.com/dns-query",
    "quad9": "https://dns.quad9.net/dns-query",
    "google": "https://dns.google/dns-query",
}


def _state_path() -> str:
    return os.path.join(get_settings().data_dir, "dns.json")


def _load() -> DnsConfig:
    try:
        with open(_state_path()) as fh:
            return DnsConfig(**json.load(fh))
    except (OSError, json.JSONDecodeError, TypeError):
        return DnsConfig(upstream=["1.1.1.1", "9.9.9.9"], mode="classic")


def _save(cfg: DnsConfig) -> None:
    os.makedirs(get_settings().data_dir, exist_ok=True)
    with open(_state_path(), "w") as fh:
        json.dump(cfg.model_dump(), fh)


@router.get("/upstream", response_model=DnsConfig)
async def get_config(_: str = Depends(require_user)) -> DnsConfig:
    return _load()


@router.put("/upstream", response_model=DnsConfig)
async def set_config(cfg: DnsConfig, _: str = Depends(require_user)) -> DnsConfig:
    _save(cfg)
    return cfg


@router.get("/providers")
async def providers(_: str = Depends(require_user)) -> dict:
    return {"doh": DOH_PROVIDERS}
