"use client";
import { Info, AlertTriangle, XCircle } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/primitives";
import { useApi } from "@/hooks/useApi";
import { relativeTime } from "@/lib/utils";
import type { AppEvent } from "@/lib/types";

const ICONS = {
  info: { Icon: Info, cls: "text-primary border-primary/30" },
  warn: { Icon: AlertTriangle, cls: "text-warn border-warn/30" },
  error: { Icon: XCircle, cls: "text-bad border-bad/30" },
};

export function EventTimeline() {
  const { data } = useApi<AppEvent[]>("/dashboard/events?limit=50");
  const events = data ?? [];

  return (
    <Card>
      <CardHeader><CardTitle>Ereignisse</CardTitle></CardHeader>
      <CardContent>
        {events.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted">Keine Ereignisse</p>
        ) : (
          <ul className="space-y-0">
            {events.map((e, i) => {
              const { Icon, cls } = ICONS[e.severity] ?? ICONS.info;
              return (
                <li key={i} className="flex gap-3 pb-4 last:pb-0">
                  <div className="flex flex-col items-center">
                    <span className={`rounded-full border-2 bg-surface p-1.5 ${cls}`}>
                      <Icon size={13} />
                    </span>
                    {i < events.length - 1 && <span className="w-px flex-1 bg-border" />}
                  </div>
                  <div className="flex-1 pb-1">
                    <p className="text-sm text-fg">{e.detail}</p>
                    <p className="text-xs text-muted">{relativeTime(e.ts)}</p>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
