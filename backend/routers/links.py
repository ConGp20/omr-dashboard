"""WAN link listing and per-link configuration."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from auth import require_user
from config import get_settings
from deps import get_aggregator
from schemas import LinkStatus, LinkUpdate
from services import demo_data
from services.router_proxy import RouterProxy

router = APIRouter(prefix="/links", tags=["links"])


@router.get("", response_model=list[LinkStatus])
async def list_links(_: str = Depends(require_user)) -> list[LinkStatus]:
    status = await get_aggregator().status()
    return sorted(status.links, key=lambda l: l.priority)


@router.put("/{link_id}", response_model=LinkStatus)
async def update_link(link_id: str, update: LinkUpdate, _: str = Depends(require_user)) -> LinkStatus:
    settings = get_settings()
    if settings.demo:
        demo_data.set_link(
            link_id,
            enabled=update.enabled,
            label=update.label,
            priority=update.priority,
            type=update.type,
        )
    else:
        router_proxy = RouterProxy()
        values: dict = {}
        if update.label is not None:
            values["name"] = update.label
        if update.enabled is not None:
            values["enabled"] = "1" if update.enabled else "0"
        if values:
            await router_proxy.uci_set("openmptcprouter", link_id, values)
            await router_proxy.uci_commit("openmptcprouter")

    status = await get_aggregator().refresh()
    for link in status.links:
        if link.id == link_id:
            return link
    raise HTTPException(status_code=404, detail="Link not found")
