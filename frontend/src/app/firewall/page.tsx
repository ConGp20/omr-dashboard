"use client";
import { PageHeader } from "@/components/PageHeader";
import { OwnerBadge } from "@/components/OwnerBadge";
import { Card, CardHeader, CardTitle, CardContent, Button, Badge } from "@/components/ui/primitives";
import { useApi } from "@/hooks/useApi";
import { ShieldCheck } from "lucide-react";

interface Preset { id: string; name: string; ports: string; proto: string; description: string; }

export default function FirewallPage() {
  const { data } = useApi<{ presets: Preset[] }>("/firewall/presets");

  return (
    <div>
      <PageHeader
        title="Firewall & Ports"
        description="Welche Ports von außen erreichbar sind — ohne rohe iptables-Regeln."
        action={<OwnerBadge owner="vps" />}
      />

      {/* Zone overview */}
      <Card className="mb-4">
        <CardHeader><CardTitle>Zonen</CardTitle></CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <Badge tone="bad">net · Internet</Badge>
            <span className="text-muted">→</span>
            <Badge tone="warn">fw · VPS-Firewall</Badge>
            <span className="text-muted">→</span>
            <Badge tone="primary">vpn · Tunnel-Clients</Badge>
            <span className="text-muted">→</span>
            <Badge tone="good">lan · Lokales Netz</Badge>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2"><ShieldCheck size={16} /> Schnell-Vorlagen</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          <p className="text-xs text-muted">Öffne typische Dienste mit einem Klick. Port-Weiterleitungen ins LAN findest du unter „VPS-Endpunkt“.</p>
          {(data?.presets ?? []).map((p) => (
            <div key={p.id} className="flex items-center gap-3 rounded-lg border border-border p-2.5 text-sm">
              <span className="font-medium text-fg">{p.name}</span>
              <Badge tone="neutral">{p.ports} · {p.proto}</Badge>
              <span className="flex-1 text-xs text-muted">{p.description}</span>
              <Button size="sm" variant="outline">Öffnen</Button>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
