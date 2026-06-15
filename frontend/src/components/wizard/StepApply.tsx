"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Loader2, CheckCircle2, XCircle, PartyPopper, Rocket } from "lucide-react";
import { Button } from "@/components/ui/primitives";
import { useWizard } from "@/lib/wizardStore";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

interface ApplyStep {
  step: string;
  ok: boolean;
  detail: string;
}
interface ApplyResult {
  success: boolean;
  steps: ApplyStep[];
  download_mbps?: number;
  upload_mbps?: number;
}

export function StepApply() {
  const router = useRouter();
  const wizard = useWizard();
  const [applying, setApplying] = useState(false);
  const [result, setResult] = useState<ApplyResult | null>(null);

  const apply = async () => {
    setApplying(true);
    setResult(null);
    try {
      const r = await api.post<ApplyResult>("/wizard/apply", {
        vps_ip: wizard.vpsIp,
        omr_key: wizard.omrKey,
        router_ip: wizard.routerIp,
        router_user: wizard.routerUser,
        router_pass: wizard.routerPass,
        protocol: wizard.protocol,
        wans: wizard.wans,
        lan_ip: wizard.lanIp,
        dhcp_range: wizard.dhcpRange,
      });
      setResult(r);
      if (r.success) {
        try {
          localStorage.setItem("omr-configured", "true");
        } catch {
          /* ignore */
        }
      }
    } catch (e) {
      setResult({ success: false, steps: [{ step: "Fehler", ok: false, detail: (e as Error).message }] });
    } finally {
      setApplying(false);
    }
  };

  if (result?.success) {
    return (
      <div className="space-y-5 text-center">
        <div className="flex justify-center">
          <div className="rounded-full bg-good/15 p-4">
            <PartyPopper className="text-good" size={36} />
          </div>
        </div>
        <h2 className="text-xl font-bold text-fg">Geschafft!</h2>
        <p className="text-sm text-muted">
          Deine Verbindung ist gebündelt und aktiv.
        </p>
        {result.download_mbps != null && (
          <div className="flex justify-center gap-8">
            <div>
              <div className="text-2xl font-bold text-fg tabular">{result.download_mbps}</div>
              <div className="text-xs text-muted">Mbps Download</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-fg tabular">{result.upload_mbps}</div>
              <div className="text-xs text-muted">Mbps Upload</div>
            </div>
          </div>
        )}
        <Button onClick={() => router.push("/dashboard")} className="mx-auto">
          <Rocket size={16} /> Zum Dashboard
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <h2 className="text-lg font-bold text-fg">Verbindung herstellen</h2>
      <p className="text-sm text-muted">
        Das Dashboard überträgt jetzt die Konfiguration: Protokoll auf dem VPS
        aktivieren, VPS-IP und Schlüssel zum Router übertragen, Tunnel aufbauen.
      </p>

      <div className="rounded-lg border border-border bg-surface-2 p-4 text-sm">
        <div className="flex justify-between"><span className="text-muted">VPS</span><span className="text-fg">{wizard.vpsIp}</span></div>
        <div className="flex justify-between"><span className="text-muted">Protokoll</span><span className="text-fg">{wizard.protocol}</span></div>
        <div className="flex justify-between"><span className="text-muted">Leitungen</span><span className="text-fg">{wizard.wans.length}</span></div>
      </div>

      {result?.steps && (
        <div className="space-y-2">
          {result.steps.map((s, i) => (
            <div key={i} className="flex items-center gap-2 text-sm">
              {s.ok ? (
                <CheckCircle2 size={16} className="text-good" />
              ) : (
                <XCircle size={16} className="text-bad" />
              )}
              <span className="text-fg">{s.step}</span>
              {s.detail && <span className="text-xs text-muted">— {s.detail}</span>}
            </div>
          ))}
        </div>
      )}

      <div className="flex justify-between pt-2">
        <Button variant="ghost" onClick={wizard.back} disabled={applying}>
          <ArrowLeft size={16} /> Zurück
        </Button>
        <Button onClick={apply} disabled={applying} className={cn(applying && "opacity-80")}>
          {applying ? <Loader2 size={16} className="animate-spin" /> : <Rocket size={16} />}
          {applying ? "Verbinde…" : "Jetzt verbinden"}
        </Button>
      </div>
    </div>
  );
}
