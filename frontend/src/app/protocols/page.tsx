"use client";
import { useState } from "react";
import { Star, Network, Check, Loader2, SlidersHorizontal } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { OwnerBadge } from "@/components/OwnerBadge";
import {
  Card, CardHeader, CardTitle, CardContent, Button, Badge, Select, Input, Label,
} from "@/components/ui/primitives";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { ProtocolInfo } from "@/lib/types";

interface Scheduler { id: string; description: string; }

export default function ProtocolsPage() {
  const { data: protocols, refetch } = useApi<ProtocolInfo[]>("/protocols");
  const { data: schedData } = useApi<{ schedulers: Scheduler[] }>("/protocols/schedulers");
  const [switching, setSwitching] = useState<string | null>(null);
  const [scheduler, setScheduler] = useState("default");
  const [tune, setTune] = useState({ mtu: "", congestion: "", tfo: "" });
  const [tuning, setTuning] = useState(false);
  const [tuneMsg, setTuneMsg] = useState<string | null>(null);
  const tuneDirty = !!(tune.mtu || tune.congestion || tune.tfo);

  const applyTune = async () => {
    setTuning(true);
    setTuneMsg(null);
    try {
      const payload: Record<string, unknown> = {};
      if (tune.mtu) payload.mtu = Number(tune.mtu);
      if (tune.congestion) payload.congestion = tune.congestion;
      if (tune.tfo) payload.tcp_fast_open = tune.tfo === "on";
      const res = await api.put<{ applied: Record<string, string> }>("/protocols/tune", payload);
      const n = Object.keys(res.applied ?? {}).length;
      setTuneMsg(n ? `${n} Einstellung(en) übernommen.` : "Nichts zu ändern.");
    } catch (e) {
      setTuneMsg(`Fehler: ${(e as Error).message}`);
    } finally {
      setTuning(false);
    }
  };

  const doSwitch = async (id: string) => {
    if (!confirm("Protokoll wechseln? Die Verbindung wird für einige Sekunden unterbrochen.")) return;
    setSwitching(id);
    try {
      await api.post("/protocols/switch", { protocol: id });
      await refetch();
    } finally {
      setSwitching(null);
    }
  };

  return (
    <div>
      <PageHeader
        title="Protokoll & Scheduler"
        description="Wie deine Leitungen gebündelt und Pakete verteilt werden."
      />

      <div className="mb-5 grid grid-cols-1 gap-3 sm:grid-cols-2">
        {(protocols ?? []).map((p) => (
          <Card key={p.id} className={cn("relative", p.active && "ring-2 ring-primary")}>
            <CardContent className="pt-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Network size={16} className="text-primary" />
                  <span className="font-semibold text-fg">{p.name}</span>
                </div>
                <div className="flex gap-1">
                  {p.recommended && <Badge tone="primary"><Star size={11} /> Empfohlen</Badge>}
                  {p.active && <Badge tone="good"><Check size={11} /> Aktiv</Badge>}
                </div>
              </div>
              <p className="mt-2 text-xs text-fg"><span className="font-medium text-good">Geeignet für:</span> {p.good_for}</p>
              <p className="mt-1 text-xs text-muted"><span className="font-medium text-warn">Meide wenn:</span> {p.avoid_when}</p>
              <p className="mt-1 text-[11px] text-muted">{p.technical}</p>
              <div className="mt-3 flex items-center justify-between">
                <div className="flex gap-1 text-[11px]">
                  {p.vps_port && <span className="text-muted">Port {p.vps_port}</span>}
                  <OwnerBadge owner="sync" />
                </div>
                {!p.active && (
                  <Button size="sm" variant="outline" disabled={switching === p.id} onClick={() => doSwitch(p.id)}>
                    {switching === p.id ? <Loader2 size={14} className="animate-spin" /> : null}
                    Aktivieren
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            MPTCP-Scheduler <OwnerBadge owner="router" />
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-xs text-muted">
            Der Scheduler entscheidet, wie Pakete über die Leitungen verteilt werden.
          </p>
          <Select
            value={scheduler}
            onChange={async (e) => {
              setScheduler(e.target.value);
              await api.put("/protocols/scheduler", { scheduler: e.target.value });
            }}
            className="max-w-xs"
          >
            {(schedData?.schedulers ?? []).map((s) => (
              <option key={s.id} value={s.id}>{s.id}</option>
            ))}
          </Select>
          <div className="space-y-1.5">
            {(schedData?.schedulers ?? []).map((s) => (
              <div
                key={s.id}
                className={cn(
                  "rounded-lg border p-2.5 text-sm",
                  s.id === scheduler ? "border-primary bg-primary/5" : "border-border",
                )}
              >
                <span className="font-medium text-fg">{s.id}</span>
                <span className="ml-2 text-xs text-muted">{s.description}</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><SlidersHorizontal size={16} /> Feinabstimmung</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-xs text-muted">
            Optional — die Standardwerte passen für die meisten Anschlüsse. Ändere
            hier nur etwas, wenn Du ein konkretes Problem verfolgst. Den passenden
            MTU-Wert ermittelt <strong>Diagnose → MTU-Empfehlung</strong>.
          </p>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
            <div>
              <Label>MTU</Label>
              <Input type="number" min={576} max={9000} placeholder="z. B. 1440"
                     value={tune.mtu} onChange={(e) => setTune({ ...tune, mtu: e.target.value })} />
            </div>
            <div>
              <Label>Congestion-Control</Label>
              <Select value={tune.congestion}
                      onChange={(e) => setTune({ ...tune, congestion: e.target.value })}>
                <option value="">unverändert</option>
                <option value="bbr">BBR (empfohlen)</option>
                <option value="cubic">CUBIC</option>
                <option value="reno">Reno</option>
              </Select>
            </div>
            <div>
              <Label>TCP Fast Open</Label>
              <Select value={tune.tfo}
                      onChange={(e) => setTune({ ...tune, tfo: e.target.value })}>
                <option value="">unverändert</option>
                <option value="on">ein</option>
                <option value="off">aus</option>
              </Select>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm" onClick={applyTune} disabled={tuning || !tuneDirty}>
              {tuning ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />} Übernehmen
            </Button>
            {tuneMsg && <span className="text-xs text-muted">{tuneMsg}</span>}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
