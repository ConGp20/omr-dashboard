"use client";
import { useRef, useState } from "react";
import { ArrowUpCircle, CheckCircle2, Download, Upload, Save } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardHeader, CardTitle, CardContent, Button, Badge } from "@/components/ui/primitives";
import { useApi } from "@/hooks/useApi";
import type { ComponentVersion } from "@/lib/types";

function Versions() {
  const { data } = useApi<{ components: ComponentVersion[] }>("/system/versions");
  return (
    <Card>
      <CardHeader><CardTitle>Versionen & Updates</CardTitle></CardHeader>
      <CardContent>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-muted">
              <th className="pb-2 font-medium">Komponente</th>
              <th className="pb-2 font-medium">Installiert</th>
              <th className="pb-2 font-medium">Verfügbar</th>
              <th className="pb-2 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {(data?.components ?? []).map((c) => (
              <tr key={c.component} className="border-t border-border">
                <td className="py-2 text-fg">{c.component}</td>
                <td className="py-2 tabular text-muted">{c.installed}</td>
                <td className="py-2 tabular text-muted">{c.available ?? "—"}</td>
                <td className="py-2">
                  {c.update_available ? (
                    <Badge tone="warn"><ArrowUpCircle size={11} /> Update</Badge>
                  ) : (
                    <Badge tone="good"><CheckCircle2 size={11} /> Aktuell</Badge>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}

function BackupRestore() {
  const fileRef = useRef<HTMLInputElement>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const backup = async () => {
    const pw = prompt("Passwort zum Verschlüsseln des Backups:");
    if (!pw) return;
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("password", pw);
      const res = await fetch("/api/system/backup", { method: "POST", body: fd });
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "config.omr-backup.json.gz";
      a.click();
      URL.revokeObjectURL(url);
      setMsg("Backup heruntergeladen.");
    } finally {
      setBusy(false);
    }
  };

  const restore = async (file: File) => {
    const pw = prompt("Passwort des Backups:");
    if (!pw) return;
    setBusy(true);
    setMsg(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("password", pw);
      const res = await fetch("/api/system/restore", { method: "POST", body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail);
      setMsg(`Wiederhergestellt: ${(data.applied ?? []).join(", ") || "OK"}`);
    } catch (e) {
      setMsg(`Fehler: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <CardHeader><CardTitle className="flex items-center gap-2"><Save size={16} /> Backup & Wiederherstellung</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        <p className="text-xs text-muted">
          Sichere die komplette Konfiguration (VPS + Router) in einer verschlüsselten
          Datei. Ideal für anlassbezogenen Einsatz — in zwei Minuten wieder einsatzbereit.
        </p>
        <div className="flex gap-2">
          <Button variant="outline" onClick={backup} disabled={busy}>
            <Download size={14} /> Backup erstellen
          </Button>
          <Button variant="outline" onClick={() => fileRef.current?.click()} disabled={busy}>
            <Upload size={14} /> Wiederherstellen
          </Button>
          <input
            ref={fileRef}
            type="file"
            accept=".gz,.json"
            className="hidden"
            onChange={(e) => e.target.files?.[0] && restore(e.target.files[0])}
          />
        </div>
        {msg && <p className="text-sm text-fg">{msg}</p>}
      </CardContent>
    </Card>
  );
}

export default function SystemPage() {
  return (
    <div>
      <PageHeader title="System" description="Versionen, Updates und Konfigurations-Backups." />
      <div className="space-y-4">
        <Versions />
        <BackupRestore />
      </div>
    </div>
  );
}
