"use client";
import { ArrowDown, ArrowUp } from "lucide-react";
import { LinkIcon } from "@/components/LinkIcon";
import { Sparkline } from "@/components/dashboard/Sparkline";
import { Badge } from "@/components/ui/primitives";
import { useDashboardStore } from "@/lib/store";
import { formatBps, linkTypeLabel, cn } from "@/lib/utils";
import type { LinkStatus } from "@/lib/types";

const STATE_META = {
  up: { tone: "good" as const, label: "Aktiv", bar: "bg-good", iconBg: "bg-good/15" },
  degraded: { tone: "warn" as const, label: "Beeinträchtigt", bar: "bg-warn", iconBg: "bg-warn/15" },
  down: { tone: "bad" as const, label: "Ausgefallen", bar: "bg-bad", iconBg: "bg-bad/15" },
  disabled: { tone: "neutral" as const, label: "Deaktiviert", bar: "bg-muted", iconBg: "bg-surface-2" },
};

// Reference capacities (bps) per type for the relative fill bar.
const CAP: Record<string, number> = {
  fiber: 100e6, dsl: 50e6, lte: 50e6, "5g": 100e6, ethernet: 100e6, satellite: 50e6, other: 50e6,
};

const TONE_TEXT = { good: "text-good", warn: "text-warn", bad: "text-bad", neutral: "text-muted" } as const;

export function LinkCard({ link }: { link: LinkStatus }) {
  const meta = STATE_META[link.state];
  const cap = CAP[link.type] ?? 50e6;
  const fill = Math.min(100, (link.rx_bps / cap) * 100);
  const history = useDashboardStore((s) => s.linkHistory[link.id]) ?? [];

  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2.5">
          <div className={cn("rounded-lg p-2", meta.iconBg)}>
            <LinkIcon type={link.type} />
          </div>
          <div>
            <div className="font-semibold leading-tight text-fg">{link.label}</div>
            <div className="text-xs text-muted">{linkTypeLabel(link.type)}</div>
          </div>
        </div>
        <Badge tone={meta.tone}>
          <span className={cn("h-1.5 w-1.5 rounded-full", meta.bar)} />
          {meta.label}
        </Badge>
      </div>

      {/* Throughput bar */}
      <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-surface-2">
        <div
          className={cn("h-full rounded-full transition-all duration-700", meta.bar)}
          style={{ width: `${link.state === "disabled" ? 0 : fill}%` }}
        />
      </div>

      <div className="mt-3 flex items-center justify-between text-sm">
        <span className="flex items-center gap-1 text-fg">
          <ArrowDown size={13} className="text-muted" />
          <span className="tabular font-medium">{formatBps(link.rx_bps)}</span>
        </span>
        {history.length > 1 && (
          <Sparkline values={history} className={cn("h-5 w-20", TONE_TEXT[meta.tone])} />
        )}
        <span className="flex items-center gap-1 text-fg">
          <ArrowUp size={13} className="text-muted" />
          <span className="tabular font-medium">{formatBps(link.tx_bps)}</span>
        </span>
      </div>

      <div className="mt-2 flex justify-between border-t border-border pt-2 text-xs text-muted">
        <span>Latenz: <span className="tabular text-fg">{link.latency_ms != null ? `${link.latency_ms} ms` : "—"}</span></span>
        <span>Verlust: <span className="tabular text-fg">{link.packet_loss_pct != null ? `${link.packet_loss_pct}%` : "—"}</span></span>
      </div>
    </div>
  );
}
