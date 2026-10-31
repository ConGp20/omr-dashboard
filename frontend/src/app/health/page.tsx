"use client";
import Link from "next/link";
import { AlertTriangle, ArrowRight, CheckCircle2, Info, RefreshCw, ShieldAlert, Stethoscope } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardContent, Button, Badge } from "@/components/ui/primitives";
import { useApi } from "@/hooks/useApi";
import type { Finding, HealthReport } from "@/lib/types";

const CATEGORY_LABELS: Record<string, string> = {
  security: "Sicherheit",
  connectivity: "Verbindung",
  usage: "Datenverbrauch",
  alerting: "Benachrichtigungen",
  performance: "Leistung",
  general: "Allgemein",
};

// Full class names, so Tailwind's static extraction keeps them in the build.
const SEVERITY = {
  error: { tone: "bad" as const, label: "Handlungsbedarf", Icon: ShieldAlert, color: "text-bad" },
  warn: { tone: "warn" as const, label: "Hinweis", Icon: AlertTriangle, color: "text-warn" },
  info: { tone: "primary" as const, label: "Empfehlung", Icon: Info, color: "text-primary" },
};

function FindingCard({ f }: { f: Finding }) {
  const { tone, label, Icon, color } = SEVERITY[f.severity];
  return (
    <Card>
      <CardContent className="space-y-2 p-4">
        <div className="flex flex-wrap items-center gap-2">
          <span className={color}><Icon size={16} /></span>
          <h3 className="flex-1 text-sm font-semibold text-fg">{f.title}</h3>
          <Badge tone={tone}>{label}</Badge>
          <Badge tone="neutral">{CATEGORY_LABELS[f.category] ?? f.category}</Badge>
        </div>
        <p className="text-sm text-muted">{f.detail}</p>
        <div className="flex flex-wrap items-center gap-2 rounded-lg bg-surface-2 p-2.5">
          <span className="text-xs font-medium text-fg">Empfohlen:</span>
          <span className="flex-1 text-xs text-muted">{f.action}</span>
          {f.page && (
            <Link href={f.page}>
              <Button size="sm" variant="outline">
                Dorthin <ArrowRight size={13} />
              </Button>
            </Link>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export default function HealthPage() {
  const { data, loading, refetch } = useApi<HealthReport>("/health-check");

  return (
    <div>
      <PageHeader
        title="Systemcheck"
        description="Auffälligkeiten, Empfehlungen und passende Einstellungen — rein beratend, nichts wird blockiert."
        action={
          <Button size="sm" variant="outline" onClick={refetch} disabled={loading}>
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> Erneut prüfen
          </Button>
        }
      />

      {!data ? (
        <p className="text-sm text-muted">Prüfe Konfiguration…</p>
      ) : (
        <>
          <div className="mb-4 grid grid-cols-3 gap-3">
            {[
              { n: data.errors, label: "Handlungsbedarf", tone: "text-bad" },
              { n: data.warnings, label: "Hinweise", tone: "text-warn" },
              { n: data.infos, label: "Empfehlungen", tone: "text-primary" },
            ].map((s) => (
              <Card key={s.label}>
                <CardContent className="p-4">
                  <div className={`tabular text-2xl font-bold ${s.tone}`}>{s.n}</div>
                  <div className="text-xs text-muted">{s.label}</div>
                </CardContent>
              </Card>
            ))}
          </div>

          {data.findings.length === 0 ? (
            <Card>
              <CardContent className="flex items-center gap-3 p-6">
                <CheckCircle2 size={24} className="text-good" />
                <div>
                  <p className="text-sm font-semibold text-fg">Alles unauffällig</p>
                  <p className="text-xs text-muted">
                    {data.checked} Prüfungen ohne Befund. Sicherheit, Verbindung,
                    Datenverbrauch und Benachrichtigungen sind sinnvoll eingestellt.
                  </p>
                </div>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-3">
              {data.findings.map((f) => <FindingCard key={f.id} f={f} />)}
              <p className="flex items-center gap-1.5 pt-1 text-xs text-muted">
                <Stethoscope size={13} />
                {data.checked} Prüfungen durchlaufen. Alle Punkte sind Empfehlungen —
                Du kannst sie ignorieren, ohne dass etwas blockiert wird.
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
