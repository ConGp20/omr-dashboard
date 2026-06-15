"use client";
import Link from "next/link";
import { Router, Server, RefreshCw } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/primitives";
import { useApi } from "@/hooks/useApi";
import type { ConfigMap, ConfigMapItem } from "@/lib/types";

const COLUMNS = [
  { key: "router" as const, title: "Router (Peer-Seite)", Icon: Router, tone: "text-blue-500 dark:text-blue-400" },
  { key: "vps" as const, title: "VPS (Server-Seite)", Icon: Server, tone: "text-purple-500 dark:text-purple-400" },
  { key: "sync" as const, title: "Auto-Sync (VPS → Router)", Icon: RefreshCw, tone: "text-amber-500 dark:text-amber-400" },
];

function Item({ item }: { item: ConfigMapItem }) {
  const inner = (
    <div className="rounded-lg border border-border bg-surface-2 p-2.5 transition hover:border-primary/40">
      <div className="text-sm font-medium text-fg">{item.label}</div>
      <div className="text-xs text-muted">{item.description}</div>
    </div>
  );
  return item.page ? <Link href={item.page}>{inner}</Link> : inner;
}

export default function ConfigMapPage() {
  const { data } = useApi<ConfigMap>("/config-map");

  return (
    <div>
      <PageHeader
        title="Konfigurations-Karte"
        description="Wer konfiguriert was? Welche Einstellung liegt auf dem Router, welche auf dem VPS, und was wird automatisch synchronisiert."
      />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {COLUMNS.map(({ key, title, Icon, tone }) => (
          <Card key={key}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Icon size={16} className={tone} /> {title}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {(data?.[key] ?? []).map((item) => (
                <Item key={item.key} item={item} />
              ))}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
