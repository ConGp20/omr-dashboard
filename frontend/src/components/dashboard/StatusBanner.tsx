"use client";
import { ShieldCheck, ShieldAlert, ShieldX, ArrowDown, ArrowUp } from "lucide-react";
import { useDashboardStore } from "@/lib/store";
import { formatBps, cn } from "@/lib/utils";

const CONFIG = {
  bonded: {
    tone: "good", icon: ShieldCheck, title: "BONDED",
    text: "Alle Verbindungen gebündelt und aktiv",
  },
  degraded: {
    tone: "warn", icon: ShieldAlert, title: "DEGRADED",
    text: "Eingeschränkt — nicht alle Leitungen optimal",
  },
  offline: {
    tone: "bad", icon: ShieldX, title: "OFFLINE",
    text: "Keine aktive Tunnelverbindung",
  },
} as const;

export function StatusBanner() {
  const status = useDashboardStore((s) => s.status);
  const state = status?.state ?? "offline";
  const c = CONFIG[state];
  const Icon = c.icon;

  const toneClasses = {
    good: "from-good/20 to-good/5 border-good/30",
    warn: "from-warn/20 to-warn/5 border-warn/30",
    bad: "from-bad/20 to-bad/5 border-bad/30",
  }[c.tone];

  const iconTone = { good: "text-good", warn: "text-warn", bad: "text-bad" }[c.tone];

  return (
    <div
      data-tour-step="status-banner"
      className={cn(
        "flex flex-col gap-4 rounded-2xl border bg-gradient-to-br p-5 sm:flex-row sm:items-center sm:justify-between",
        toneClasses,
      )}
    >
      <div className="flex items-center gap-4">
        <div className="relative">
          <Icon size={40} className={iconTone} />
          {state === "bonded" && (
            <span className="absolute inset-0 animate-pulse-ring rounded-full border-2 border-good" />
          )}
        </div>
        <div>
          <div className="flex items-center gap-2">
            <span className={cn("text-2xl font-bold tracking-tight", iconTone)}>{c.title}</span>
            {status && (
              <span className="text-sm text-muted">
                {status.active_links}/{status.total_links} Leitungen
              </span>
            )}
          </div>
          <p className="text-sm text-muted">{c.text}</p>
        </div>
      </div>

      <div className="flex gap-6">
        <div className="text-right">
          <div className="flex items-center justify-end gap-1 text-xs text-muted">
            <ArrowDown size={12} /> Download
          </div>
          <div className="tabular text-2xl font-bold text-fg">
            {formatBps(status?.total_rx_bps ?? 0)}
          </div>
        </div>
        <div className="text-right">
          <div className="flex items-center justify-end gap-1 text-xs text-muted">
            <ArrowUp size={12} /> Upload
          </div>
          <div className="tabular text-2xl font-bold text-fg">
            {formatBps(status?.total_tx_bps ?? 0)}
          </div>
        </div>
      </div>
    </div>
  );
}
