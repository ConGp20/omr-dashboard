"use client";
import { useState } from "react";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/primitives";
import { EventTimeline } from "@/components/monitoring/EventTimeline";
import { useApi } from "@/hooks/useApi";
import { cn } from "@/lib/utils";
import type { MetricPoint } from "@/lib/types";

const PERIODS = ["1h", "6h", "24h", "7d"];
const COLORS = ["#3b82f6", "#22c55e", "#f59e0b", "#a855f7", "#ef4444"];

interface MetricsResponse { period: string; points: MetricPoint[]; }

function pivot(points: MetricPoint[]) {
  // group by timestamp -> { ts, [linkId]: rx_mbps }
  const byTs = new Map<number, Record<string, number>>();
  const links = new Set<string>();
  for (const p of points) {
    links.add(p.link_id);
    const row = byTs.get(p.ts) ?? { ts: p.ts };
    row[p.link_id] = +(p.rx_bps / 1e6).toFixed(2);
    byTs.set(p.ts, row);
  }
  const rows = [...byTs.values()].sort((a, b) => a.ts - b.ts).map((r) => ({
    ...r,
    time: new Date(r.ts * 1000).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }),
  }));
  return { rows, links: [...links] };
}

export default function MonitoringPage() {
  const [period, setPeriod] = useState("24h");
  const { data } = useApi<MetricsResponse>(`/dashboard/metrics/${period}`);
  const { rows, links } = pivot(data?.points ?? []);

  return (
    <div>
      <PageHeader title="Verlauf" description="Bandbreite und Ereignisse über die Zeit." />

      <Card className="mb-4">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Bandbreite (Download, Mbps)</CardTitle>
          <div className="flex gap-1">
            {PERIODS.map((p) => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={cn(
                  "rounded-md px-2.5 py-1 text-xs font-medium transition",
                  p === period ? "bg-primary text-white" : "bg-surface-2 text-muted hover:text-fg",
                )}
              >
                {p}
              </button>
            ))}
          </div>
        </CardHeader>
        <CardContent>
          {rows.length === 0 ? (
            <p className="py-16 text-center text-sm text-muted">
              Noch keine Verlaufsdaten — sammle ein paar Minuten.
            </p>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={rows}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgb(var(--border))" />
                <XAxis dataKey="time" tick={{ fontSize: 11, fill: "rgb(var(--muted))" }} />
                <YAxis tick={{ fontSize: 11, fill: "rgb(var(--muted))" }} />
                <Tooltip
                  contentStyle={{
                    background: "rgb(var(--surface))", border: "1px solid rgb(var(--border))",
                    borderRadius: 8, fontSize: 12, color: "rgb(var(--fg))",
                  }}
                  labelStyle={{ color: "rgb(var(--fg))" }}
                />
                <Legend wrapperStyle={{ fontSize: 12, color: "rgb(var(--fg))" }} />
                {links.map((id, i) => (
                  <Area
                    key={id}
                    type="monotone"
                    dataKey={id}
                    stackId="1"
                    stroke={COLORS[i % COLORS.length]}
                    fill={COLORS[i % COLORS.length]}
                    fillOpacity={0.25}
                  />
                ))}
              </AreaChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      <EventTimeline />
    </div>
  );
}
