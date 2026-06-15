"use client";
import { PageHeader } from "@/components/PageHeader";
import { OwnerBadge } from "@/components/OwnerBadge";
import { LinkIcon } from "@/components/LinkIcon";
import { Card, CardContent, Toggle, Select, Input, Badge } from "@/components/ui/primitives";
import { useDashboardStore } from "@/lib/store";
import { api } from "@/lib/api";
import { formatBps, linkTypeLabel } from "@/lib/utils";
import type { LinkType } from "@/lib/types";

const TYPES: LinkType[] = ["fiber", "dsl", "lte", "5g", "ethernet", "satellite", "other"];

export default function LinksPage() {
  const status = useDashboardStore((s) => s.status);
  const links = [...(status?.links ?? [])].sort((a, b) => a.priority - b.priority);

  const update = async (id: string, patch: Record<string, unknown>) => {
    await api.put(`/links/${id}`, patch);
  };

  return (
    <div>
      <PageHeader
        title="Verbindungen"
        description="Deine WAN-Leitungen — benennen, priorisieren, vorübergehend deaktivieren."
        action={<OwnerBadge owner="router" />}
      />
      <div className="space-y-3">
        {links.map((l) => (
          <Card key={l.id}>
            <CardContent className="flex flex-wrap items-center gap-3 pt-4">
              <LinkIcon type={l.type} size={20} />
              <Input
                defaultValue={l.label}
                className="w-44"
                onBlur={(e) => update(l.id, { label: e.target.value })}
              />
              <Select
                defaultValue={l.type}
                className="w-32"
                onChange={(e) => update(l.id, { type: e.target.value })}
              >
                {TYPES.map((t) => (
                  <option key={t} value={t}>{linkTypeLabel(t)}</option>
                ))}
              </Select>
              <div className="flex-1 text-sm text-muted">
                {l.ip && <span className="tabular">{l.ip}</span>}
                {l.state !== "disabled" && (
                  <span className="ml-3 tabular">
                    ↓ {formatBps(l.rx_bps)} · ↑ {formatBps(l.tx_bps)} · {l.latency_ms ?? "—"}ms
                  </span>
                )}
              </div>
              <Badge tone={l.state === "up" ? "good" : l.state === "degraded" ? "warn" : l.state === "down" ? "bad" : "neutral"}>
                {l.state}
              </Badge>
              <label className="flex items-center gap-2 text-xs text-muted">
                Aktiv
                <Toggle checked={l.enabled} onChange={(v) => update(l.id, { enabled: v })} />
              </label>
            </CardContent>
          </Card>
        ))}
        {links.length === 0 && (
          <p className="py-8 text-center text-sm text-muted">Warte auf Verbindungsdaten…</p>
        )}
      </div>
    </div>
  );
}
