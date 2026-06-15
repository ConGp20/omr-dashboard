"use client";
import Link from "next/link";
import { Network } from "lucide-react";
import { StatusBanner } from "@/components/dashboard/StatusBanner";
import { LinkCard } from "@/components/dashboard/LinkCard";
import { TopologyDiagram } from "@/components/dashboard/TopologyDiagram";
import { RecentEvents } from "@/components/dashboard/RecentEvents";
import { Badge } from "@/components/ui/primitives";
import { useDashboardStore } from "@/lib/store";

export default function DashboardPage() {
  const status = useDashboardStore((s) => s.status);
  const links = status?.links ?? [];

  return (
    <div className="space-y-5">
      <StatusBanner />

      {/* Active protocol chip */}
      {status?.tunnel && (
        <div className="flex items-center gap-2 text-sm text-muted">
          Aktives Protokoll:
          <Link href="/protocols">
            <Badge tone="primary">
              <Network size={12} /> {status.tunnel.protocol}
              {status.tunnel.encryption ? ` · ${status.tunnel.encryption}` : ""}
            </Badge>
          </Link>
        </div>
      )}

      {/* Link cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {links.map((l) => (
          <LinkCard key={l.id} link={l} />
        ))}
        {links.length === 0 && (
          <div className="col-span-full rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted">
            Warte auf Verbindungsdaten…
          </div>
        )}
      </div>

      {/* Topology + events */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-fg">Netzwerk-Topologie</h2>
            <span className="text-xs text-muted">Knoten anklicken zum Konfigurieren</span>
          </div>
          <TopologyDiagram />
        </div>
        <RecentEvents />
      </div>
    </div>
  );
}
