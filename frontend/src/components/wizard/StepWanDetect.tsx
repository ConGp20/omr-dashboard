"use client";
import { useState } from "react";
import { ArrowRight, ArrowLeft, Loader2, Search } from "lucide-react";
import { Button, Input, Label, Select } from "@/components/ui/primitives";
import { OwnerBadge } from "@/components/OwnerBadge";
import { LinkIcon } from "@/components/LinkIcon";
import { useWizard } from "@/lib/wizardStore";
import { api } from "@/lib/api";
import type { LinkType, WizardWan } from "@/lib/types";

const TYPES: LinkType[] = ["fiber", "dsl", "lte", "5g", "ethernet", "satellite", "other"];

export function StepWanDetect() {
  const { routerIp, routerUser, routerPass, wans, set, next, back } = useWizard();
  const [detecting, setDetecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const detect = async () => {
    setDetecting(true);
    setError(null);
    try {
      const r = await api.post<{ wans: WizardWan[]; error?: string }>("/wizard/detect-wans", {
        router_ip: routerIp,
        router_user: routerUser,
        router_pass: routerPass,
      });
      if (r.error) setError(r.error);
      else set({ wans: r.wans });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setDetecting(false);
    }
  };

  const updateWan = (id: string, patch: Partial<WizardWan>) =>
    set({ wans: wans.map((w) => (w.id === id ? { ...w, ...patch } : w)) });

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold text-fg">Leitungen erkennen</h2>
        <OwnerBadge owner="router" />
      </div>
      <p className="text-sm text-muted">
        Das Dashboard verbindet sich mit dem Router und erkennt die WAN-Leitungen
        automatisch. Benenne sie und passe bei Bedarf den Typ an.
      </p>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div>
          <Label>Router-IP</Label>
          <Input value={routerIp} onChange={(e) => set({ routerIp: e.target.value })} />
        </div>
        <div>
          <Label>Benutzer</Label>
          <Input value={routerUser} onChange={(e) => set({ routerUser: e.target.value })} />
        </div>
        <div>
          <Label>Passwort</Label>
          <Input
            type="password"
            value={routerPass}
            onChange={(e) => set({ routerPass: e.target.value })}
          />
        </div>
      </div>

      <Button variant="outline" onClick={detect} disabled={detecting}>
        {detecting ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />}
        Leitungen erkennen
      </Button>

      {error && <p className="text-sm text-bad">{error}</p>}

      {wans.length > 0 && (
        <div className="space-y-2">
          {wans.map((w) => (
            <div
              key={w.id}
              className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-surface-2 p-3"
            >
              <LinkIcon type={w.detected_type} />
              <Input
                className="w-40"
                value={w.label}
                onChange={(e) => updateWan(w.id, { label: e.target.value })}
              />
              <Select
                className="w-32"
                value={w.detected_type}
                onChange={(e) => updateWan(w.id, { detected_type: e.target.value as LinkType })}
              >
                {TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </Select>
              <span className="text-xs text-muted">
                {w.interface} {w.ip ? `· ${w.ip}` : ""} {w.up ? "· aktiv" : "· down"}
              </span>
            </div>
          ))}
        </div>
      )}

      <div className="flex justify-between pt-2">
        <Button variant="ghost" onClick={back}>
          <ArrowLeft size={16} /> Zurück
        </Button>
        <Button onClick={next} disabled={wans.length === 0}>
          Weiter <ArrowRight size={16} />
        </Button>
      </div>
    </div>
  );
}
