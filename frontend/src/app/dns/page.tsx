"use client";
import { useState } from "react";
import { PageHeader } from "@/components/PageHeader";
import { OwnerBadge } from "@/components/OwnerBadge";
import { Card, CardHeader, CardTitle, CardContent, Button, Input, Select } from "@/components/ui/primitives";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import type { DnsConfig } from "@/lib/types";

interface Dns extends DnsConfig {}

export default function DnsPage() {
  const { data, refetch } = useApi<Dns>("/dns/upstream");
  const providers = useApi<{ doh: Record<string, string> }>("/dns/providers");
  const [form, setForm] = useState<Dns | null>(null);
  const cfg = form ?? data;

  const save = async () => {
    if (!cfg) return;
    await api.put("/dns/upstream", cfg);
    setForm(null);
    refetch();
  };

  if (!cfg) return null;
  return (
    <div>
      <PageHeader title="DNS" description="Namensauflösung und Datenschutz." action={<OwnerBadge owner="router" />} />
      <Card>
        <CardHeader><CardTitle>Upstream-Resolver</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div>
            <label className="text-xs font-medium text-muted">Modus</label>
            <Select value={cfg.mode} onChange={(e) => setForm({ ...cfg, mode: e.target.value as Dns["mode"] })} className="max-w-xs">
              <option value="classic">Klassisch (Port 53)</option>
              <option value="doh">DNS over HTTPS (DoH)</option>
              <option value="dot">DNS over TLS (DoT)</option>
            </Select>
          </div>
          <div>
            <label className="text-xs font-medium text-muted">Server (kommagetrennt)</label>
            <Input
              value={cfg.upstream.join(", ")}
              onChange={(e) => setForm({ ...cfg, upstream: e.target.value.split(",").map((s) => s.trim()) })}
            />
          </div>

          {cfg.mode === "doh" && (
            <div>
              <label className="text-xs font-medium text-muted">Bekannte DoH-Anbieter</label>
              <div className="mt-1 flex flex-wrap gap-2">
                {Object.entries(providers.data?.doh ?? {}).map(([id, url]) => {
                  const active = cfg.upstream.includes(url);
                  return (
                    <Button
                      key={id} size="sm" variant={active ? "primary" : "outline"}
                      onClick={() => setForm({ ...cfg, upstream: active ? [] : [url] })}
                    >
                      {id}
                    </Button>
                  );
                })}
              </div>
              <p className="mt-1 text-xs text-muted">
                Ein Klick setzt die passende Adresse ein — danach noch speichern.
              </p>
            </div>
          )}

          <Button size="sm" onClick={save} disabled={!form}>Speichern</Button>
        </CardContent>
      </Card>
    </div>
  );
}
