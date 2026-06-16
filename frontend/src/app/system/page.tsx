"use client";
import { useRef, useState } from "react";
import { ArrowUpCircle, CheckCircle2, Download, Upload, Save, KeyRound, Wifi } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardHeader, CardTitle, CardContent, Button, Badge, Input, Label } from "@/components/ui/primitives";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import type { ComponentVersion, ConnectionSettings, ConnectionTestResult, SecuritySettings } from "@/lib/types";

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

function ConnectionSettingsSection() {
  const { data, refetch } = useApi<ConnectionSettings>("/settings/connection");
  const [form, setForm] = useState<{ router_ip: string; router_user: string; router_pass: string; omr_admin_key: string } | null>(null);
  const [test, setTest] = useState<ConnectionTestResult | null>(null);
  const [busy, setBusy] = useState(false);

  if (!data) return null;
  const vals = form ?? { router_ip: data.router_ip, router_user: data.router_user, router_pass: "", omr_admin_key: "" };

  const save = async () => {
    setBusy(true);
    try {
      const payload: Record<string, string> = { router_ip: vals.router_ip, router_user: vals.router_user };
      if (vals.router_pass) payload.router_pass = vals.router_pass;
      if (vals.omr_admin_key) payload.omr_admin_key = vals.omr_admin_key;
      await api.put("/settings/connection", payload);
      setForm(null);
      refetch();
    } finally {
      setBusy(false);
    }
  };

  const runTest = async () => {
    setBusy(true);
    try {
      setTest(await api.post<ConnectionTestResult>("/settings/connection/test"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <CardHeader><CardTitle className="flex items-center gap-2"><Wifi size={16} /> Verbindung (Router & VPS)</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        <p className="text-xs text-muted">
          Diese Zugangsdaten hat der Setup-Assistent einmal gesetzt — hier lassen sie sich
          jederzeit ändern, ohne den Container neu zu starten.
        </p>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          <div>
            <Label>Router-IP</Label>
            <Input value={vals.router_ip} onChange={(e) => setForm({ ...vals, router_ip: e.target.value })} />
          </div>
          <div>
            <Label>Router-Benutzer</Label>
            <Input value={vals.router_user} onChange={(e) => setForm({ ...vals, router_user: e.target.value })} />
          </div>
          <div>
            <Label className="flex items-center gap-1.5">Router-Passwort {data.router_pass_set && <Badge tone="good">gesetzt</Badge>}</Label>
            <Input type="password" placeholder="•••• (leer = unverändert)" value={vals.router_pass} onChange={(e) => setForm({ ...vals, router_pass: e.target.value })} />
          </div>
          <div>
            <Label className="flex items-center gap-1.5">OMR-Admin-Key {data.omr_admin_key_set && <Badge tone="good">gesetzt</Badge>}</Label>
            <Input type="password" placeholder="•••• (leer = unverändert)" value={vals.omr_admin_key} onChange={(e) => setForm({ ...vals, omr_admin_key: e.target.value })} />
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" onClick={save} disabled={!form || busy}>Speichern</Button>
          <Button size="sm" variant="outline" onClick={runTest} disabled={busy}>Verbindung testen</Button>
          {test && (
            <span className="text-xs text-muted">
              Router: {test.router_reachable ? "✓" : "✗"} {test.router_detail} · OMR-Admin: {test.omr_admin_reachable ? "✓" : "✗"} {test.omr_admin_detail}
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function SecuritySettingsSection() {
  const { data, refetch } = useApi<SecuritySettings>("/settings/security");
  const [form, setForm] = useState<{ dashboard_user: string; dashboard_pass: string; jwt_secret: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  if (!data) return null;
  const vals = form ?? { dashboard_user: data.dashboard_user, dashboard_pass: "", jwt_secret: "" };

  const save = async () => {
    setBusy(true);
    setMsg(null);
    try {
      const payload: Record<string, string> = { dashboard_user: vals.dashboard_user };
      if (vals.dashboard_pass) payload.dashboard_pass = vals.dashboard_pass;
      if (vals.jwt_secret) payload.jwt_secret = vals.jwt_secret;
      await api.put("/settings/security", payload);
      const loggedOut = !!vals.jwt_secret;
      setForm(null);
      refetch();
      setMsg(loggedOut ? "Gespeichert — alle Sitzungen wurden abgemeldet (JWT-Secret geändert)." : "Gespeichert.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <CardHeader><CardTitle className="flex items-center gap-2"><KeyRound size={16} /> Sicherheit</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        <p className="text-xs text-muted">
          Dashboard-Login und Session-Signatur. Das Ändern des JWT-Secrets meldet
          alle aktiven Sitzungen sofort ab.
        </p>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          <div>
            <Label>Dashboard-Benutzer</Label>
            <Input value={vals.dashboard_user} onChange={(e) => setForm({ ...vals, dashboard_user: e.target.value })} />
          </div>
          <div>
            <Label className="flex items-center gap-1.5">Dashboard-Passwort {data.dashboard_pass_set && <Badge tone="good">gesetzt</Badge>}</Label>
            <Input type="password" placeholder="•••• (leer = unverändert)" value={vals.dashboard_pass} onChange={(e) => setForm({ ...vals, dashboard_pass: e.target.value })} />
          </div>
          <div className="sm:col-span-2">
            <Label className="flex items-center gap-1.5">JWT-Secret {data.jwt_secret_set && <Badge tone="good">gesetzt</Badge>}</Label>
            <Input type="password" placeholder="•••• (leer = unverändert)" value={vals.jwt_secret} onChange={(e) => setForm({ ...vals, jwt_secret: e.target.value })} />
          </div>
        </div>
        <Button size="sm" onClick={save} disabled={!form || busy}>Speichern</Button>
        {msg && <p className="text-sm text-fg">{msg}</p>}
      </CardContent>
    </Card>
  );
}

export default function SystemPage() {
  return (
    <div>
      <PageHeader title="System" description="Versionen, Updates, Zugangsdaten und Konfigurations-Backups." />
      <div className="space-y-4">
        <ConnectionSettingsSection />
        <SecuritySettingsSection />
        <Versions />
        <BackupRestore />
      </div>
    </div>
  );
}
