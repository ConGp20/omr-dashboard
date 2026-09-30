"use client";
import { useState } from "react";
import { Bell, Send, Save, MessageCircle, Webhook, Mail } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardHeader, CardTitle, CardContent, Button, Badge, Input, Label, Select, Toggle } from "@/components/ui/primitives";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import type { AlertConfigPublic, AlertTestResult } from "@/lib/types";

type Form = Record<string, string | number | boolean>;

export default function AlertsPage() {
  const { data, refetch } = useApi<AlertConfigPublic>("/alerts/config");
  const [form, setForm] = useState<Form>({});
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [test, setTest] = useState<AlertTestResult | null>(null);

  if (!data) return <p className="text-sm text-muted">Lade Konfiguration…</p>;

  // Effective value: pending form edit wins, else the stored config.
  const v = (k: string, fallback: string | number | boolean) =>
    k in form ? form[k] : fallback;
  const set = (k: string, val: string | number | boolean) => setForm({ ...form, [k]: val });
  const dirty = Object.keys(form).length > 0;

  const save = async () => {
    setBusy(true);
    setMsg(null);
    try {
      await api.put("/alerts/config", form);
      setForm({});
      setTest(null);
      refetch();
      setMsg("Gespeichert.");
    } catch (e) {
      setMsg(`Fehler: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  const runTest = async () => {
    setBusy(true);
    setMsg(null);
    try {
      if (dirty) await api.put("/alerts/config", form);
      setForm({});
      refetch();
      setTest(await api.post<AlertTestResult>("/alerts/test"));
    } catch (e) {
      setMsg(`Fehler: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  const secretPlaceholder = "•••• (leer = unverändert)";

  return (
    <div>
      <PageHeader
        title="Alarme"
        description="Benachrichtigung bei WAN-Ausfall oder erreichtem Datenlimit."
        action={
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={runTest} disabled={busy}>
              <Send size={14} /> Test senden
            </Button>
            <Button size="sm" onClick={save} disabled={!dirty || busy}>
              <Save size={14} /> Speichern
            </Button>
          </div>
        }
      />

      {(msg || test) && (
        <div className="mb-4 rounded-lg border border-border bg-surface px-3 py-2 text-sm">
          {msg && <p className="text-fg">{msg}</p>}
          {test && (
            Object.keys(test.results).length === 0
              ? <p className="text-muted">Kein Kanal aktiv — bitte zuerst einen Kanal aktivieren und speichern.</p>
              : Object.entries(test.results).map(([ch, r]) => (
                  <p key={ch} className="text-muted"><span className="text-fg">{ch}</span>: {r}</p>
                ))
          )}
        </div>
      )}

      <div className="space-y-4">
        <Card>
          <CardHeader><CardTitle>Auslösung</CardTitle></CardHeader>
          <CardContent className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <Label>Ab welcher Schwere benachrichtigen</Label>
              <Select
                value={String(v("min_severity", data.min_severity))}
                onChange={(e) => set("min_severity", e.target.value)}
                className="mt-1"
              >
                <option value="warn">Warnung &amp; Fehler (empfohlen)</option>
                <option value="error">Nur Fehler</option>
              </Select>
            </div>
            <div>
              <Label>Wiederholsperre (Minuten)</Label>
              <Input
                type="number" min={0} max={1440} className="mt-1"
                value={Number(v("cooldown_minutes", data.cooldown_minutes))}
                onChange={(e) => set("cooldown_minutes", Number(e.target.value))}
              />
              <p className="mt-1 text-xs text-muted">
                Dieselbe Meldung wird höchstens einmal pro Zeitfenster gesendet —
                schützt vor Nachrichtenfluten bei einer flatternden Leitung.
                0 = keine Sperre.
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Telegram */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span className="flex items-center gap-2"><MessageCircle size={16} /> Telegram</span>
              <Toggle checked={!!v("telegram_enabled", data.telegram_enabled)}
                onChange={(c) => set("telegram_enabled", c)} />
            </CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <div>
              <Label className="flex items-center gap-1.5">Bot-Token {data.telegram_token_set && <Badge tone="good">gesetzt</Badge>}</Label>
              <Input type="password" placeholder={secretPlaceholder}
                value={String(v("telegram_token", ""))}
                onChange={(e) => set("telegram_token", e.target.value)} />
            </div>
            <div>
              <Label>Chat-ID</Label>
              <Input value={String(v("telegram_chat_id", data.telegram_chat_id ?? ""))}
                onChange={(e) => set("telegram_chat_id", e.target.value)} />
            </div>
          </CardContent>
        </Card>

        {/* Webhook */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span className="flex items-center gap-2"><Webhook size={16} /> Webhook</span>
              <Toggle checked={!!v("webhook_enabled", data.webhook_enabled)}
                onChange={(c) => set("webhook_enabled", c)} />
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Label>URL (erhält JSON per POST)</Label>
            <Input placeholder="https://…" value={String(v("webhook_url", data.webhook_url ?? ""))}
              onChange={(e) => set("webhook_url", e.target.value)} />
          </CardContent>
        </Card>

        {/* E-Mail */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span className="flex items-center gap-2"><Mail size={16} /> E-Mail (SMTP)</span>
              <Toggle checked={!!v("email_enabled", data.email_enabled)}
                onChange={(c) => set("email_enabled", c)} />
            </CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <div>
              <Label>SMTP-Server</Label>
              <Input value={String(v("smtp_host", data.smtp_host ?? ""))}
                onChange={(e) => set("smtp_host", e.target.value)} />
            </div>
            <div>
              <Label>Port</Label>
              <Input type="number" value={Number(v("smtp_port", data.smtp_port))}
                onChange={(e) => set("smtp_port", Number(e.target.value))} />
            </div>
            <div>
              <Label>Benutzer</Label>
              <Input value={String(v("smtp_user", data.smtp_user ?? ""))}
                onChange={(e) => set("smtp_user", e.target.value)} />
            </div>
            <div>
              <Label className="flex items-center gap-1.5">Passwort {data.smtp_pass_set && <Badge tone="good">gesetzt</Badge>}</Label>
              <Input type="password" placeholder={secretPlaceholder}
                value={String(v("smtp_pass", ""))}
                onChange={(e) => set("smtp_pass", e.target.value)} />
            </div>
            <div>
              <Label>Absender</Label>
              <Input placeholder="omr@example.com" value={String(v("email_from", data.email_from ?? ""))}
                onChange={(e) => set("email_from", e.target.value)} />
            </div>
            <div>
              <Label>Empfänger</Label>
              <Input placeholder="you@example.com" value={String(v("email_to", data.email_to ?? ""))}
                onChange={(e) => set("email_to", e.target.value)} />
            </div>
            <label className="flex items-center gap-2 text-xs text-muted sm:col-span-2">
              <Toggle checked={!!v("smtp_tls", data.smtp_tls)} onChange={(c) => set("smtp_tls", c)} />
              STARTTLS verwenden
            </label>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
