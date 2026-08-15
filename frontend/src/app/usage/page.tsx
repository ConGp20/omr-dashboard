"use client";
import { useState } from "react";
import { Gauge, Save } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardHeader, CardTitle, CardContent, Button, Badge, Input, Label } from "@/components/ui/primitives";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import { formatBytes } from "@/lib/utils";
import type { LinkUsage, UsageResponse } from "@/lib/types";

function monthLabel(month: string): string {
  const [y, m] = month.split("-");
  const names = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
    "August", "September", "Oktober", "November", "Dezember"];
  return `${names[Number(m) - 1] ?? m} ${y}`;
}

/**
 * Usage bar with a projection marker.
 *
 * The filled part is what has actually been used; the tick shows where the
 * month is heading at the current rate. Seeing the forecast cross the end of
 * the bar is the moment to act — long before the cap is actually hit.
 */
function UsageBar({ pct, projectedPct, over }: {
  pct: number; projectedPct?: number | null; over: "none" | "warn" | "cap";
}) {
  const tone = over === "cap" ? "bg-bad" : over === "warn" ? "bg-warn" : "bg-primary";
  const marker = projectedPct != null ? Math.min(100, projectedPct) : null;
  return (
    <div className="relative h-2 w-full overflow-hidden rounded-full bg-surface-2">
      <div className={`h-full rounded-full ${tone} transition-all`}
           style={{ width: `${Math.min(100, pct)}%` }} />
      {marker != null && marker > pct && (
        <span
          className="absolute top-0 h-2 w-0.5 bg-fg/60"
          style={{ left: `calc(${marker}% - 1px)` }}
          title={`Hochrechnung Monatsende: ${projectedPct?.toFixed(0)} %`}
        />
      )}
    </div>
  );
}

function LinkUsageCard({ link, onSaved }: { link: LinkUsage; onSaved: () => void }) {
  const [cap, setCap] = useState(link.cap_gb != null ? String(link.cap_gb) : "");
  const [warn, setWarn] = useState(String(link.warn_pct));
  const [busy, setBusy] = useState(false);

  const dirty = (link.cap_gb != null ? String(link.cap_gb) : "") !== cap || String(link.warn_pct) !== warn;

  const save = async () => {
    setBusy(true);
    try {
      await api.put(`/dashboard/usage/${encodeURIComponent(link.link_id)}/quota`, {
        cap_gb: cap === "" ? 0 : Number(cap),
        warn_pct: Number(warn) || 80,
      });
      onSaved();
    } finally {
      setBusy(false);
    }
  };

  const over = link.over_cap ? "cap" : link.over_warn ? "warn" : "none";
  const pct = link.used_pct ?? 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between gap-2">
          <span>{link.label}</span>
          {over === "cap" && <Badge tone="bad">Limit erreicht</Badge>}
          {over === "warn" && <Badge tone="warn">Warnschwelle</Badge>}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-end justify-between">
          <span className="text-2xl font-bold tabular text-fg">{formatBytes(link.total_bytes)}</span>
          <span className="text-xs text-muted">
            {link.cap_gb ? `von ${link.cap_gb} GB${link.used_pct != null ? ` · ${link.used_pct.toFixed(0)}%` : ""}` : "kein Limit gesetzt"}
          </span>
        </div>
        {link.cap_gb ? <UsageBar pct={pct} projectedPct={link.projected_pct} over={over} /> : null}
        <div className="flex flex-wrap gap-4 text-xs text-muted">
          <span>↓ {formatBytes(link.rx_bytes)}</span>
          <span>↑ {formatBytes(link.tx_bytes)}</span>
        </div>
        {link.cap_gb ? (
          <p className={`text-xs ${link.projected_over_cap ? "text-warn" : "text-muted"}`}>
            {link.projected_over_cap ? "⚠ " : ""}
            Hochrechnung Monatsende: {formatBytes(link.projected_bytes)}
            {link.projected_pct != null && ` (${link.projected_pct.toFixed(0)} % des Limits)`}
            {link.projected_over_cap && " — beim aktuellen Tempo wird das Limit überschritten."}
          </p>
        ) : null}
        <div className="grid grid-cols-2 gap-2 border-t border-border pt-3">
          <div>
            <Label>Monatslimit (GB)</Label>
            <Input type="number" min={0} placeholder="kein Limit" value={cap}
              onChange={(e) => setCap(e.target.value)} />
          </div>
          <div>
            <Label>Warnschwelle (%)</Label>
            <Input type="number" min={1} max={100} value={warn}
              onChange={(e) => setWarn(e.target.value)} />
          </div>
        </div>
        <Button size="sm" onClick={save} disabled={!dirty || busy}>
          <Save size={14} /> Speichern
        </Button>
      </CardContent>
    </Card>
  );
}

export default function UsagePage() {
  const { data, refetch } = useApi<UsageResponse>("/dashboard/usage");

  return (
    <div>
      <PageHeader
        title="Datenverbrauch"
        description="Monatliches Volumen pro WAN — mit Warnschwelle für ISP-Limits."
        action={data && (
          <div className="text-right">
            <div className="text-xs text-muted">
              {monthLabel(data.month)} · Tag {data.day_of_month} von {data.days_in_month}
            </div>
            <div className="flex items-center gap-1.5 text-sm font-semibold text-fg">
              <Gauge size={15} /> {formatBytes(data.total_bytes)} gesamt
            </div>
          </div>
        )}
      />
      {!data ? (
        <p className="text-sm text-muted">Lade Verbrauchsdaten…</p>
      ) : data.links.length === 0 ? (
        <p className="text-sm text-muted">Noch keine Verbrauchsdaten erfasst.</p>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {data.links.map((l) => (
            <LinkUsageCard key={l.link_id} link={l} onSaved={refetch} />
          ))}
        </div>
      )}
    </div>
  );
}
