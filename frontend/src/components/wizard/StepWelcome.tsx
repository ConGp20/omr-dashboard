"use client";
import { useRef, useState } from "react";
import { Layers, Upload, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/primitives";
import { useWizard } from "@/lib/wizardStore";

export function StepWelcome() {
  const next = useWizard((s) => s.next);
  const fileRef = useRef<HTMLInputElement>(null);
  const [restoring, setRestoring] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onRestore = async (file: File) => {
    const pw = prompt("Passwort des Backups eingeben:");
    if (!pw) return;
    setRestoring(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("password", pw);
      const res = await fetch("/api/wizard/restore-backup", { method: "POST", body: fd });
      if (!res.ok) throw new Error((await res.json()).detail ?? "Fehler");
      alert("Backup gültig — Konfiguration wird übernommen.");
      try {
        localStorage.setItem("omr-configured", "true");
      } catch {
        /* ignore */
      }
      window.location.href = "/dashboard";
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setRestoring(false);
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <div className="rounded-xl bg-primary/15 p-3">
          <Layers className="text-primary" size={28} />
        </div>
        <div>
          <h2 className="text-lg font-bold text-fg">Willkommen bei OpenMPTCProuter</h2>
          <p className="text-sm text-muted">In wenigen Schritten einsatzbereit</p>
        </div>
      </div>

      <p className="text-sm leading-relaxed text-fg">
        Du richtest gleich eine <strong>gebündelte Internetverbindung</strong> ein,
        die mehrere Leitungen (DSL, LTE, 5G …) zu einer schnellen, ausfallsicheren
        Verbindung kombiniert. Der Router bündelt die Leitungen, der VPS führt sie
        wieder zusammen und stellt eine feste öffentliche IP bereit.
      </p>

      <div className="rounded-lg border border-border bg-surface-2 p-4 text-sm text-muted">
        <p className="font-medium text-fg">Du brauchst:</p>
        <ul className="mt-1 list-inside list-disc space-y-0.5">
          <li>Einen Router mit OpenMPTCProuter (MiniPC, Raspberry Pi …)</li>
          <li>Einen VPS mit installiertem OpenMPTCProuter-VPS</li>
          <li>Den Server-Schlüssel des VPS (aus <code>/root/openmptcprouter_config.txt</code>)</li>
        </ul>
      </div>

      {error && <p className="text-sm text-bad">{error}</p>}

      <div className="flex flex-col gap-3 sm:flex-row">
        <Button onClick={next} className="flex-1">
          Neu einrichten <ArrowRight size={16} />
        </Button>
        <Button
          variant="outline"
          className="flex-1"
          disabled={restoring}
          onClick={() => fileRef.current?.click()}
        >
          <Upload size={16} /> {restoring ? "Prüfe…" : "Backup wiederherstellen"}
        </Button>
        <input
          ref={fileRef}
          type="file"
          accept=".gz,.json"
          className="hidden"
          onChange={(e) => e.target.files?.[0] && onRestore(e.target.files[0])}
        />
      </div>
    </div>
  );
}
