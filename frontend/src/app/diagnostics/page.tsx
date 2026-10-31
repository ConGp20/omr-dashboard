"use client";
import { useState } from "react";
import { Activity, Gauge, History, Loader2, Router, Ruler, Server } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardHeader, CardTitle, CardContent, Button, Input } from "@/components/ui/primitives";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";

interface PingResult {
  source: string; target: string;
  min_ms?: number; avg_ms?: number; max_ms?: number; loss_pct?: number; raw: string;
}
interface SpeedResult { download_mbps: number; upload_mbps: number; server?: string; error?: string; }
interface MtuResult { results: { link: string; mtu: number; note: string }[]; note?: string; }
interface SpeedHistory { results: { ts: number; rx_mbps?: number; tx_mbps?: number }[] }

export default function DiagnosticsPage() {
  const [target, setTarget] = useState("1.1.1.1");
  const [pinging, setPinging] = useState(false);
  const [pings, setPings] = useState<PingResult[]>([]);
  const [testing, setTesting] = useState(false);
  const [speed, setSpeed] = useState<SpeedResult | null>(null);
  const [mtu, setMtu] = useState<MtuResult | null>(null);
  const [mtuBusy, setMtuBusy] = useState(false);
  const history = useApi<SpeedHistory>("/diagnostics/speedtest/history");

  const findMtu = async () => {
    setMtuBusy(true);
    try {
      setMtu(await api.post<MtuResult>("/diagnostics/mtu"));
    } finally {
      setMtuBusy(false);
    }
  };

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
      history.refetch();
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

        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><Ruler size={16} /> MTU-Empfehlung</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <p className="text-xs text-muted">
              Eine zu große MTU führt zu fragmentierten Paketen und wirkt wie eine
              „langsame, aber verbundene“ Leitung. Der Test ermittelt pro WAN den
              größten Wert, der unfragmentiert durchgeht.
            </p>
            <Button onClick={findMtu} disabled={mtuBusy} variant="outline">
              {mtuBusy ? <Loader2 size={14} className="animate-spin" /> : <Ruler size={14} />}
              {mtuBusy ? "Ermittle…" : "MTU ermitteln"}
            </Button>
            {mtu && (
              mtu.results.length === 0 ? (
                <p className="text-xs text-muted">{mtu.note ?? "Keine Ergebnisse."}</p>
              ) : (
                <div className="space-y-1">
                  {mtu.results.map((r) => (
                    <div key={r.link} className="flex items-center gap-2 rounded-lg border border-border p-2 text-sm">
                      <span className="font-medium text-fg">{r.link}</span>
                      <span className="tabular text-fg">{r.mtu}</span>
                      <span className="flex-1 text-xs text-muted">{r.note}</span>
                    </div>
                  ))}
                  <p className="text-xs text-muted">
                    Übernehmen kannst Du den Wert unter <strong>Protokoll → Feinabstimmung</strong>.
                  </p>
                </div>
              )
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><History size={16} /> Frühere Messungen</CardTitle></CardHeader>
          <CardContent>
            {(history.data?.results ?? []).length === 0 ? (
              <p className="text-xs text-muted">
                Noch keine Messungen gespeichert. Jeder Geschwindigkeitstest wird hier
                mitgeschrieben, damit Du Veränderungen über die Zeit siehst.
              </p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-muted">
                    <th className="pb-2 font-medium">Zeitpunkt</th>
                    <th className="pb-2 font-medium">Download</th>
                    <th className="pb-2 font-medium">Upload</th>
                  </tr>
                </thead>
                <tbody>
                  {(history.data?.results ?? []).map((r, i) => (
                    <tr key={`${r.ts}-${i}`} className="border-t border-border">
                      <td className="py-1.5 text-muted">{new Date(r.ts * 1000).toLocaleString("de-DE")}</td>
                      <td className="py-1.5 tabular text-fg">{r.rx_mbps?.toFixed(1) ?? "—"} Mbps</td>
                      <td className="py-1.5 tabular text-fg">{r.tx_mbps?.toFixed(1) ?? "—"} Mbps</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
