"use client";
import { ArrowRight, ArrowLeft } from "lucide-react";
import { Button, Input, Label } from "@/components/ui/primitives";
import { OwnerBadge } from "@/components/OwnerBadge";
import { useWizard } from "@/lib/wizardStore";

export function StepLan() {
  const { lanIp, dhcpRange, set, next, back } = useWizard();

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold text-fg">Lokales Netzwerk</h2>
        <OwnerBadge owner="router" />
      </div>
      <p className="text-sm text-muted">
        Bestätige die LAN-Einstellungen des Routers. In den meisten Fällen kannst du
        die Vorgaben übernehmen.
      </p>

      <div className="space-y-3">
        <div>
          <Label>Router LAN-IP</Label>
          <Input value={lanIp} onChange={(e) => set({ lanIp: e.target.value })} />
        </div>
        <div>
          <Label>DHCP-Bereich</Label>
          <Input value={dhcpRange} onChange={(e) => set({ dhcpRange: e.target.value })} />
          <p className="mt-1 text-xs text-muted">
            Adressbereich, den der Router an Geräte vergibt.
          </p>
        </div>
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
