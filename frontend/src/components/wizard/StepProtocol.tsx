"use client";
import { useEffect, useState } from "react";
import { ArrowRight, ArrowLeft, Star } from "lucide-react";
import { Button, Badge } from "@/components/ui/primitives";
import { OwnerBadge } from "@/components/OwnerBadge";
import { useWizard } from "@/lib/wizardStore";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { ProtocolInfo } from "@/lib/types";

export function StepProtocol() {
  const { protocol, wans, set, next, back } = useWizard();
  const [protocols, setProtocols] = useState<ProtocolInfo[]>([]);

  useEffect(() => {
    api.get<ProtocolInfo[]>("/protocols").then(setProtocols).catch(() => {});
  }, []);

  // Recommend based on link count detected in the previous step.
  const recommended = wans.length <= 1 ? "glorytun_tcp" : "shadowsocks";

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold text-fg">Protokoll wählen</h2>
        <div className="flex gap-1">
          <OwnerBadge owner="vps" />
          <OwnerBadge owner="sync" />
        </div>
      </div>
      <p className="text-sm text-muted">
        Das Tunnelprotokoll bestimmt, wie deine Leitungen zum VPS gebündelt werden.
        Der Schlüssel wird auf dem VPS erzeugt und automatisch zum Router übertragen.
      </p>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {protocols.map((p) => {
          const isRec = p.id === recommended;
          const selected = protocol === p.id;
          return (
            <button
              key={p.id}
              onClick={() => set({ protocol: p.id })}
              className={cn(
                "rounded-xl border-2 p-4 text-left transition",
                selected
                  ? "border-primary bg-primary/5"
                  : "border-border bg-surface hover:border-primary/40",
              )}
            >
              <div className="flex items-center justify-between">
                <span className="font-semibold text-fg">{p.name}</span>
                {isRec && (
                  <Badge tone="primary">
                    <Star size={11} /> Empfohlen
                  </Badge>
                )}
              </div>
              <p className="mt-2 text-xs text-fg">
                <span className="font-medium text-good">Geeignet für:</span> {p.good_for}
              </p>
              <p className="mt-1 text-xs text-muted">
                <span className="font-medium text-warn">Meide wenn:</span> {p.avoid_when}
              </p>
              {p.vps_port && (
                <p className="mt-2 text-[11px] text-muted">VPS-Port {p.vps_port}</p>
              )}
            </button>
          );
        })}
      </div>

      <div className="flex justify-between pt-2">
        <Button variant="ghost" onClick={back}>
          <ArrowLeft size={16} /> Zurück
        </Button>
        <Button onClick={next}>
          Weiter <ArrowRight size={16} />
        </Button>
      </div>
    </div>
  );
}
