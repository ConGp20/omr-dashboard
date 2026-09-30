"use client";
import Link from "next/link";
import { AlertTriangle, ArrowRight, Info, ShieldAlert } from "lucide-react";
import { useApi } from "@/hooks/useApi";
import type { HealthReport } from "@/lib/types";

/**
 * Non-blocking summary of the configuration advisor.
 *
 * Deliberately a single quiet line rather than a modal: it points at something
 * worth improving without standing between the user and their dashboard. It
 * disappears entirely when there is nothing to say.
 */
export function AdvisorBanner() {
  const { data } = useApi<HealthReport>("/health-check");
  if (!data || data.findings.length === 0) return null;

  const worst = data.findings[0];
  const style = worst.severity === "error"
    ? { border: "border-bad/40", bg: "bg-bad/10", color: "text-bad", Icon: ShieldAlert }
    : worst.severity === "warn"
      ? { border: "border-warn/40", bg: "bg-warn/10", color: "text-warn", Icon: AlertTriangle }
      : { border: "border-primary/40", bg: "bg-primary/10", color: "text-primary", Icon: Info };

  const more = data.findings.length - 1;

  return (
    <Link
      href="/health"
      className={`mb-4 flex items-center gap-3 rounded-xl border ${style.border} ${style.bg} px-3 py-2.5 transition hover:opacity-90`}
    >
      <span className={style.color}><style.Icon size={17} /></span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-fg">{worst.title}</p>
        <p className="truncate text-xs text-muted">
          {worst.action}
          {more > 0 && ` · ${more} weitere${more === 1 ? "r" : ""} Punkt${more === 1 ? "" : "e"}`}
        </p>
      </div>
      <span className="shrink-0 text-xs text-muted">Systemcheck</span>
      <ArrowRight size={15} className="shrink-0 text-muted" />
    </Link>
  );
}
