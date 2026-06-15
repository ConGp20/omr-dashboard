"use client";
import { useState } from "react";
import { ArrowRight, ArrowLeft, CheckCircle2, XCircle, Loader2 } from "lucide-react";
import { Button, Input, Label } from "@/components/ui/primitives";
import { OwnerBadge } from "@/components/OwnerBadge";
import { useWizard } from "@/lib/wizardStore";
import { api } from "@/lib/api";

interface ConnectResult {
  success: boolean;
  vps_version?: string;
  current_vpn?: string;
  protocols_available: string[];
  error?: string;
}

export function StepVpsConnect() {
  const { vpsIp, omrKey, set, next, back } = useWizard();
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState<ConnectResult | null>(null);

  const test = async () => {
    setTesting(true);
    setResult(null);
    try {
      const r = await api.post<ConnectResult>("/wizard/connect", {
        vps_ip: vpsIp,
        omr_key: omrKey,
      });
      setResult(r);
      if (r.success) {
        set({ vpsVersion: r.vps_version, protocolsAvailable: r.protocols_available });
      }
    } catch (e) {
      setResult({ success: false, protocols_available: [], error: (e as Error).message });
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold text-fg">VPS verbinden</h2>
        <OwnerBadge owner="vps" />
      </div>
      <p className="text-sm text-muted">
        Gib die Adresse deines VPS und den Server-Schlüssel ein. Diese Daten liegen
        auf dem VPS — das Dashboard liest die übrige Konfiguration automatisch aus.
      </p>

      <div className="space-y-3">
        <div>
          <Label>VPS IP-Adresse oder Domain</Label>
          <Input
            placeholder="z. B. 198.51.100.7"
            value={vpsIp}
            onChange={(e) => set({ vpsIp: e.target.value })}
          />
        </div>
        <div>
          <Label>Server-Schlüssel (OMR Key)</Label>
          <Input
            type="password"
            placeholder="aus /root/openmptcprouter_config.txt"
            value={omrKey}
            onChange={(e) => set({ omrKey: e.target.value })}
          />
        </div>
      </div>

      <Button variant="outline" onClick={test} disabled={!vpsIp || testing}>
        {testing ? <Loader2 size={16} className="animate-spin" /> : null}
        Verbindung testen
      </Button>

      {result && (
        <div
          className={`flex items-start gap-2 rounded-lg border p-3 text-sm ${
            result.success ? "border-good/30 bg-good/10" : "border-bad/30 bg-bad/10"
          }`}
        >
          {result.success ? (
            <CheckCircle2 size={18} className="mt-0.5 shrink-0 text-good" />
          ) : (
            <XCircle size={18} className="mt-0.5 shrink-0 text-bad" />
          )}
          <div>
            {result.success ? (
              <>
                <p className="font-medium text-good">Verbunden!</p>
                <p className="text-muted">
                  VPS-Version {result.vps_version} · Protokolle:{" "}
                  {result.protocols_available.join(", ")}
                </p>
              </>
            ) : (
              <p className="text-bad">{result.error}</p>
            )}
          </div>
        </div>
      )}

      <div className="flex justify-between pt-2">
        <Button variant="ghost" onClick={back}>
          <ArrowLeft size={16} /> Zurück
        </Button>
        <Button onClick={next} disabled={!result?.success}>
          Weiter <ArrowRight size={16} />
        </Button>
      </div>
    </div>
  );
}
