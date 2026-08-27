"use client";
import { useState } from "react";
import { PageHeader } from "@/components/PageHeader";
import { OwnerBadge } from "@/components/OwnerBadge";
import { Card, CardHeader, CardTitle, CardContent, Button, Badge, Input, Label, Select } from "@/components/ui/primitives";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import { ShieldCheck, Plus, Trash2, ListChecks } from "lucide-react";
import type { FirewallRule } from "@/lib/types";

interface Preset { id: string; name: string; ports: string; proto: string; description: string; }

const EMPTY: FirewallRule = {
  action: "allow", src_zone: "net", dest_zone: "fw",
  proto: "tcp", port: "", description: "", enabled: true,
};

export default function FirewallPage() {
  const presets = useApi<{ presets: Preset[] }>("/firewall/presets");
  const rules = useApi<FirewallRule[]>("/firewall/rules");
  const [form, setForm] = useState<FirewallRule>(EMPTY);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const openPreset = async (p: Preset) => {
    setBusy(true);
    setMsg(null);
    try {
      await api.post<FirewallRule>("/firewall/rules", {
        ...EMPTY,
        proto: p.proto === "udp" ? "udp" : p.proto === "tcp/udp" ? "tcp/udp" : "tcp",
        port: p.ports,
        description: p.name,
      });
      rules.refetch();
      setMsg(`„${p.name}“ geöffnet (${p.ports}/${p.proto}).`);
    } catch (e) {
      setMsg(`Fehler: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  const addRule = async () => {
    setBusy(true);
    setMsg(null);
    try {
      await api.post<FirewallRule>("/firewall/rules", form);
      setForm(EMPTY);
      rules.refetch();
      setMsg("Regel angelegt.");
    } catch (e) {
      setMsg(`Fehler: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: string) => {
    setBusy(true);
    try {
      await api.del(`/firewall/rules/${encodeURIComponent(id)}`);
      rules.refetch();
    } catch (e) {
      setMsg(`Fehler: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  const openPorts = new Set((rules.data ?? []).map((r) => `${r.port}/${r.proto}`));

  return (
    <div>
      <PageHeader
        title="Firewall & Ports"
        description="Welche Ports von außen erreichbar sind — ohne rohe iptables-Regeln."
        action={<OwnerBadge owner="vps" />}
      />

      {msg && (
        <div className="mb-4 rounded-lg border border-border bg-surface px-3 py-2 text-sm text-fg">{msg}</div>
      )}

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
          <p className="mt-2 text-xs text-muted">
            Regeln hier steuern den Zugang <em>zum VPS selbst</em>. Weiterleitungen
            ins LAN dahinter richtest Du unter „VPS-Endpunkt“ ein.
          </p>
        </CardContent>
      </Card>

      {/* Active rules */}
      <Card className="mb-4">
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><ListChecks size={16} /> Aktive Regeln</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {rules.data === null ? (
            <p className="text-xs text-muted">Lade…</p>
          ) : rules.data.length === 0 ? (
            <p className="text-xs text-muted">
              Keine eigenen Regeln — es gilt die Grundkonfiguration (nur SSH und die
              Tunnel-Ports sind offen). Das ist der sichere Ausgangszustand.
            </p>
          ) : (
            rules.data.map((r) => (
              <div key={r.id ?? `${r.port}-${r.proto}`}
                   className="flex flex-wrap items-center gap-2 rounded-lg border border-border p-2.5 text-sm">
                <Badge tone={r.action === "allow" ? "good" : "bad"}>
                  {r.action === "allow" ? "erlaubt" : "blockiert"}
                </Badge>
                <span className="tabular font-medium text-fg">{r.port}/{r.proto}</span>
                <span className="text-xs text-muted">{r.src_zone} → {r.dest_zone}</span>
                <span className="flex-1 text-xs text-muted">{r.description}</span>
                {r.id && (
                  <Button size="sm" variant="outline" disabled={busy}
                          onClick={() => remove(r.id as string)}>
                    <Trash2 size={13} /> Entfernen
                  </Button>
                )}
              </div>
            ))
          )}
        </CardContent>
      </Card>

      {/* Presets */}
      <Card className="mb-4">
        <CardHeader><CardTitle className="flex items-center gap-2"><ShieldCheck size={16} /> Schnell-Vorlagen</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          <p className="text-xs text-muted">Öffne typische Dienste mit einem Klick.</p>
          {(presets.data?.presets ?? []).map((p) => {
            const already = openPorts.has(`${p.ports}/${p.proto}`);
            return (
              <div key={p.id} className="flex flex-wrap items-center gap-3 rounded-lg border border-border p-2.5 text-sm">
                <span className="font-medium text-fg">{p.name}</span>
                <Badge tone="neutral">{p.ports} · {p.proto}</Badge>
                <span className="flex-1 text-xs text-muted">{p.description}</span>
                {already ? (
                  <Badge tone="good">bereits offen</Badge>
                ) : (
                  <Button size="sm" variant="outline" disabled={busy} onClick={() => openPreset(p)}>
                    Öffnen
                  </Button>
                )}
              </div>
            );
          })}
        </CardContent>
      </Card>

      {/* Custom rule */}
      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2"><Plus size={16} /> Eigene Regel</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
            <div>
              <Label>Aktion</Label>
              <Select value={form.action}
                      onChange={(e) => setForm({ ...form, action: e.target.value as FirewallRule["action"] })}>
                <option value="allow">Erlauben</option>
                <option value="block">Blockieren</option>
              </Select>
            </div>
            <div>
              <Label>Protokoll</Label>
              <Select value={form.proto}
                      onChange={(e) => setForm({ ...form, proto: e.target.value as FirewallRule["proto"] })}>
                <option value="tcp">TCP</option>
                <option value="udp">UDP</option>
                <option value="tcp/udp">TCP + UDP</option>
              </Select>
            </div>
            <div>
              <Label>Port / Bereich</Label>
              <Input placeholder="443 oder 5000:5010" value={form.port}
                     onChange={(e) => setForm({ ...form, port: e.target.value })} />
            </div>
            <div className="sm:col-span-3">
              <Label>Beschreibung</Label>
              <Input placeholder="Wofür ist diese Regel?" value={form.description}
                     onChange={(e) => setForm({ ...form, description: e.target.value })} />
            </div>
          </div>
          <Button size="sm" onClick={addRule} disabled={busy || !form.port}>
            <Plus size={14} /> Regel anlegen
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
