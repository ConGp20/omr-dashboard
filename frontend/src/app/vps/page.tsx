"use client";
import { useState } from "react";
import { Plus, Trash2, Server, Shield, Network, Globe } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { OwnerBadge } from "@/components/OwnerBadge";
import {
  Card, CardHeader, CardTitle, CardContent,
  Button, Input, Label, Select, Toggle, Badge,
} from "@/components/ui/primitives";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import type { PortForward, ExitVpn, NatStatus, TopologyHost } from "@/lib/types";

function PortForwardSection() {
  const { data: forwards, refetch } = useApi<PortForward[]>("/vps/portforward");
  const { data: hosts } = useApi<TopologyHost[]>("/vps/hosts");
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState<PortForward>({
    description: "", proto: "tcp", src_port: 0, dest_ip: "", dest_port: 0, enabled: true,
  });

  const FIREWALL_PRESET = { label: "Firewall/VPN Durchleitung", port: 1194, proto: "udp" as const };

  const add = async () => {
    await api.post("/vps/portforward", form);
    setAdding(false);
    setForm({ description: "", proto: "tcp", src_port: 0, dest_ip: "", dest_port: 0, enabled: true });
    refetch();
  };
  const toggle = async (pf: PortForward) => {
    await api.put(`/vps/portforward/${pf.id}`, { ...pf, enabled: !pf.enabled });
    refetch();
  };
  const remove = async (id: string) => {
    await api.del(`/vps/portforward/${id}`);
    refetch();
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="flex items-center gap-2">
          <Network size={16} /> Port-Weiterleitungen <OwnerBadge owner="vps" />
        </CardTitle>
        <Button size="sm" onClick={() => setAdding(!adding)}>
          <Plus size={14} /> Neu
        </Button>
      </CardHeader>
      <CardContent className="space-y-2">
        <p className="text-xs text-muted">
          Leite Ports von der öffentlichen VPS-IP an Geräte im LAN weiter — z. B. um
          die VPN-Funktion deiner eigenen Firewall von außen erreichbar zu machen
          (Internet → VPS → Tunnel → Firewall).
        </p>

        {adding && (
          <div className="space-y-2 rounded-lg border border-border bg-surface-2 p-3">
            <button
              className="text-xs text-primary hover:underline"
              onClick={() => setForm((f) => ({ ...f, description: "Firewall VPN", proto: FIREWALL_PRESET.proto, src_port: FIREWALL_PRESET.port, dest_port: FIREWALL_PRESET.port }))}
            >
              Vorlage: {FIREWALL_PRESET.label} (Port {FIREWALL_PRESET.port})
            </button>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <div>
                <Label>Extern Port</Label>
                <Input type="number" value={form.src_port || ""} onChange={(e) => setForm({ ...form, src_port: +e.target.value })} />
              </div>
              <div>
                <Label>Protokoll</Label>
                <Select value={form.proto} onChange={(e) => setForm({ ...form, proto: e.target.value as PortForward["proto"] })}>
                  <option value="tcp">TCP</option>
                  <option value="udp">UDP</option>
                  <option value="tcp/udp">TCP/UDP</option>
                </Select>
              </div>
              <div>
                <Label>Ziel-IP (LAN)</Label>
                <Select value={form.dest_ip} onChange={(e) => setForm({ ...form, dest_ip: e.target.value })}>
                  <option value="">— wählen —</option>
                  {(hosts ?? []).map((h) => (
                    <option key={h.ip} value={h.ip}>{h.ip} {h.label ? `(${h.label})` : ""}</option>
                  ))}
                </Select>
              </div>
              <div>
                <Label>Ziel-Port</Label>
                <Input type="number" value={form.dest_port || ""} onChange={(e) => setForm({ ...form, dest_port: +e.target.value })} />
              </div>
            </div>
            <Input placeholder="Beschreibung" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            <Button size="sm" onClick={add} disabled={!form.src_port || !form.dest_ip}>Hinzufügen</Button>
          </div>
        )}

        {(forwards ?? []).map((pf) => (
          <div key={pf.id} className="flex items-center gap-3 rounded-lg border border-border p-2.5 text-sm">
            <Toggle checked={pf.enabled} onChange={() => toggle(pf)} />
            <span className="tabular font-medium text-fg">:{pf.src_port}</span>
            <Badge tone="neutral">{pf.proto}</Badge>
            <span className="text-muted">→</span>
            <span className="tabular text-fg">{pf.dest_ip}:{pf.dest_port}</span>
            <span className="min-w-0 flex-1 truncate text-xs text-muted">{pf.description}</span>
            <button onClick={() => remove(pf.id!)} className="text-muted hover:text-bad">
              <Trash2 size={15} />
            </button>
          </div>
        ))}
        {forwards?.length === 0 && !adding && (
          <p className="py-3 text-center text-sm text-muted">Keine Weiterleitungen</p>
        )}
      </CardContent>
    </Card>
  );
}

function ExitVpnSection() {
  const { data, refetch } = useApi<ExitVpn>("/vps/exit-vpn");
  const [form, setForm] = useState<ExitVpn | null>(null);
  const cfg = form ?? data;

  const save = async () => {
    if (!cfg) return;
    await api.put("/vps/exit-vpn", cfg);
    setForm(null);
    refetch();
  };

  if (!cfg) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Shield size={16} /> Exit-VPN <OwnerBadge owner="vps" />
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-xs text-muted">
          Optional: Leite den Ausgangsverkehr des VPS durch einen weiteren
          WireGuard-Server (Datenschutz-VPN oder zweiter Standort).
          Pfad: VPS → Exit-VPN → Internet.
        </p>
        <div className="flex items-center gap-3">
          <Toggle checked={cfg.enabled} onChange={(v) => setForm({ ...cfg, enabled: v })} />
          <span className="text-sm text-fg">Exit-VPN aktiv</span>
        </div>
        {cfg.enabled && (
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <div>
              <Label>Endpoint (IP:Port)</Label>
              <Input value={cfg.endpoint ?? ""} onChange={(e) => setForm({ ...cfg, endpoint: e.target.value })} />
            </div>
            <div>
              <Label>Public Key</Label>
              <Input value={cfg.public_key ?? ""} onChange={(e) => setForm({ ...cfg, public_key: e.target.value })} />
            </div>
            <div>
              <Label>Private Key</Label>
              <Input type="password" placeholder="••••" onChange={(e) => setForm({ ...cfg, private_key: e.target.value })} />
            </div>
            <div>
              <Label>Allowed IPs</Label>
              <Input value={cfg.allowed_ips} onChange={(e) => setForm({ ...cfg, allowed_ips: e.target.value })} />
            </div>
            <label className="col-span-full flex items-center gap-2 text-sm text-fg">
              <Toggle checked={cfg.kill_switch} onChange={(v) => setForm({ ...cfg, kill_switch: v })} />
              Kill-Switch (Verkehr blocken wenn Exit-VPN down)
            </label>
          </div>
        )}
        <Button size="sm" onClick={save} disabled={!form}>Speichern</Button>
      </CardContent>
    </Card>
  );
}

function NatSection() {
  const { data } = useApi<NatStatus>("/vps/nat");
  if (!data) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Globe size={16} /> NAT & Adressen <OwnerBadge owner="vps" />
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-1.5 text-sm">
        <div className="flex justify-between"><span className="text-muted">Öffentliche IPv4</span><span className="tabular text-fg">{data.public_ipv4 ?? "—"}</span></div>
        <div className="flex justify-between"><span className="text-muted">Öffentliche IPv6</span><span className="tabular text-fg">{data.public_ipv6 ?? "—"}</span></div>
        <div className="flex justify-between"><span className="text-muted">Masquerading</span><Badge tone={data.masquerade ? "good" : "neutral"}>{data.masquerade ? "aktiv" : "inaktiv"}</Badge></div>
        <div className="flex justify-between"><span className="text-muted">Tunnel-Clients</span><span className="tabular text-fg">{data.tunnel_clients.join(", ") || "—"}</span></div>
      </CardContent>
    </Card>
  );
}

export default function VpsPage() {
  return (
    <div>
      <PageHeader
        title="VPS-Endpunkt"
        description="Wo dein Verkehr wieder zusammenläuft — Routing, Weiterleitungen und Ausgang."
        action={<Badge tone="primary"><Server size={12} /> Server-Seite</Badge>}
      />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="lg:col-span-2"><PortForwardSection /></div>
        <ExitVpnSection />
        <NatSection />
      </div>
    </div>
  );
}
