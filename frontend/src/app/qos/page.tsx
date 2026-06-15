"use client";
import { useState } from "react";
import { Gamepad2, Tv, Briefcase, Download, Gauge, Plus, Trash2 } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { OwnerBadge } from "@/components/OwnerBadge";
import { Card, CardHeader, CardTitle, CardContent, Button, Input, Select } from "@/components/ui/primitives";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { DomainRule } from "@/lib/types";

const ICONS: Record<string, typeof Gauge> = {
  gaming: Gamepad2, streaming: Tv, work: Briefcase, download: Download, default: Gauge,
};
interface Profile { id: string; name: string; prioritizes: string; }

export default function QosPage() {
  const { data: profData } = useApi<{ profiles: Profile[] }>("/qos/profiles");
  const { data: active, refetch: refetchActive } = useApi<{ active: string }>("/qos/profile");
  const { data: domains, refetch: refetchDomains } = useApi<DomainRule[]>("/qos/domains");
  const [newDomain, setNewDomain] = useState("");
  const [target, setTarget] = useState("vpn");

  const setProfile = async (id: string) => {
    await api.put("/qos/profile", { active: id, available: [] });
    refetchActive();
  };
  const addDomain = async () => {
    if (!newDomain) return;
    await api.post("/qos/domains", { domain: newDomain, target });
    setNewDomain("");
    refetchDomains();
  };

  return (
    <div>
      <PageHeader
        title="QoS & Traffic"
        description="Priorisiere Anwendungen und steuere, welcher Verkehr welchen Weg nimmt."
        action={<OwnerBadge owner="router" />}
      />

      <Card className="mb-4">
        <CardHeader><CardTitle>Profil</CardTitle></CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            {(profData?.profiles ?? []).map((p) => {
              const Icon = ICONS[p.id] ?? Gauge;
              const sel = active?.active === p.id;
              return (
                <button
                  key={p.id}
                  onClick={() => setProfile(p.id)}
                  className={cn(
                    "flex flex-col items-center gap-2 rounded-xl border-2 p-4 text-center transition",
                    sel ? "border-primary bg-primary/5" : "border-border hover:border-primary/40",
                  )}
                >
                  <Icon size={24} className={sel ? "text-primary" : "text-muted"} />
                  <span className="text-sm font-medium text-fg">{p.name}</span>
                  <span className="text-[11px] leading-tight text-muted">{p.prioritizes}</span>
                </button>
              );
            })}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Domain-Routing</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          <p className="text-xs text-muted">Leite einzelne Domains gezielt über VPN, eine bestimmte Leitung oder blockiere sie.</p>
          <div className="flex gap-2">
            <Input placeholder="z. B. netflix.com" value={newDomain} onChange={(e) => setNewDomain(e.target.value)} />
            <Select value={target} onChange={(e) => setTarget(e.target.value)} className="w-40">
              <option value="vpn">Über VPN</option>
              <option value="wan">Direkt WAN1</option>
              <option value="wan2">Direkt WAN2</option>
              <option value="block">Blockieren</option>
            </Select>
            <Button onClick={addDomain}><Plus size={14} /></Button>
          </div>
          {(domains ?? []).map((d) => (
            <div key={d.id} className="flex items-center gap-3 rounded-lg border border-border p-2 text-sm">
              <span className="flex-1 text-fg">{d.domain}</span>
              <span className="text-xs text-muted">{d.target}</span>
              <button onClick={async () => { await api.del(`/qos/domains/${d.id}`); refetchDomains(); }} className="text-muted hover:text-bad">
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
