"use client";
import { useEffect, useState } from "react";
import { Info, AlertTriangle, XCircle } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { relativeTime } from "@/lib/utils";
import { useDashboardStore } from "@/lib/store";
import type { AppEvent } from "@/lib/types";

const ICONS = {
  info: { Icon: Info, cls: "text-primary" },
  warn: { Icon: AlertTriangle, cls: "text-warn" },
  error: { Icon: XCircle, cls: "text-bad" },
};

export function RecentEvents({ limit = 6 }: { limit?: number }) {
  const [events, setEvents] = useState<AppEvent[]>([]);
  const status = useDashboardStore((s) => s.status);

  useEffect(() => {
    api.get<AppEvent[]>(`/dashboard/events?limit=${limit}`).then(setEvents).catch(() => {});
  }, [limit, status?.active_links, status?.state]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Letzte Ereignisse</CardTitle>
      </CardHeader>
      <CardContent>
        {events.length === 0 ? (
          <p className="py-4 text-center text-sm text-muted">Keine Ereignisse</p>
        ) : (
          <ul className="space-y-2.5">
            {events.map((e, i) => {
              const { Icon, cls } = ICONS[e.severity] ?? ICONS.info;
              return (
                <li key={i} className="flex items-start gap-2.5 text-sm">
                  <Icon size={15} className={`mt-0.5 shrink-0 ${cls}`} />
                  <span className="flex-1 text-fg">{e.detail}</span>
                  <span className="shrink-0 text-xs text-muted">{relativeTime(e.ts)}</span>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
