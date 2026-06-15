"use client";
import { useState } from "react";
import { Activity, Gauge, Loader2, Router, Server } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardHeader, CardTitle, CardContent, Button, Input } from "@/components/ui/primitives";
import { api } from "@/lib/api";

interface PingResult {
  source: string; target: string;
  min_ms?: number; avg_ms?: number; max_ms?: number; loss_pct?: number; raw: string;
}
interface SpeedResult { download_mbps: number; upload_mbps: number; server?: string; error?: string; }

export default function DiagnosticsPage() {
  const [target, setTarget] = useState("1.1.1.1");
  const [pinging, setPinging] = useState(false);
  const [pings, setPings] = useState<PingResult[]>([]);
  const [testing, setTesting] = useState(false);
  const [speed, setSpeed] = useState<SpeedResult | null>(null);

  const ping = async () => {
    setPinging(true);
    try {
      setPings(await api.post<PingResult[]>("/diagnostics/ping", { target, count: 5 }));
    } finally {
      setPinging(false);
    }
  };
  const speedtest = async () => {
    setTesting(true);
    try {
      setSpeed(await api.post<SpeedResult>("/diagnostics/speedtest"));
    } finally {
      setTesting(false);
    }
  };

  return (
    <div>
      <PageHeader title="Diagnose" description="Finde heraus, wo ein Problem liegt — Router-Strecke oder VPS-Strecke." />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><Activity size={16} /> Ping (Router + VPS)</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <div className="flex gap-2">
              <Input value={target} onChange={(e) => setTarget(e.target.value)} placeholder="Ziel-Host" />
              <Button onClick={ping} disabled={pinging}>
                {pinging ? <Loader2 size={14} className="animate-spin" /> : "Ping"}
              </Button>
            </div>
            <div className="grid grid-cols-2 gap-3">
              {pings.map((p) => (
                <div key={p.source} className="rounded-lg border border-border p-3">
                  <div className="flex items-center gap-1.5 text-sm font-medium text-fg">
                    {p.source === "router" ? <Router size={14} /> : <Server size={14} />}
                    {p.source === "router" ? "Router" : "VPS"}
                  </div>
                  <div className="mt-1 tabular text-2xl font-bold text-fg">
                    {p.avg_ms != null ? `${p.avg_ms}` : "—"}<span className="text-sm font-normal text-muted"> ms</span>
                  </div>
                  <div className="text-xs text-muted">Verlust: {p.loss_pct ?? "—"}%</div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><Gauge size={16} /> Geschwindigkeitstest</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <Button onClick={speedtest} disabled={testing}>
              {testing ? <Loader2 size={14} className="animate-spin" /> : <Gauge size={14} />}
              {testing ? "Teste…" : "Aggregierten Test starten"}
            </Button>
            {speed && !speed.error && (
              <div className="flex gap-8">
                <div>
                  <div className="tabular text-3xl font-bold text-fg">{speed.download_mbps}</div>
                  <div className="text-xs text-muted">Mbps Download</div>
                </div>
                <div>
                  <div className="tabular text-3xl font-bold text-fg">{speed.upload_mbps}</div>
                  <div className="text-xs text-muted">Mbps Upload</div>
                </div>
              </div>
            )}
            {speed?.error && <p className="text-sm text-bad">{speed.error}</p>}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
