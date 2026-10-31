"use client";
import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { LogIn, ShieldCheck } from "lucide-react";
import { Button, Card, CardContent, Input, Label } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import type { AuthStatus } from "@/lib/types";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next") || "/dashboard";

  const [status, setStatus] = useState<AuthStatus | null>(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api
      .get<AuthStatus>("/auth/status")
      .then((s) => {
        setStatus(s);
        setUsername(s.username);
        // No password configured (or demo): there is nothing to log in to.
        if (!s.auth_required) router.replace(next);
      })
      .catch(() => setStatus({ auth_required: true, demo: false, username: "admin" }));
  }, [router, next]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail ?? "Anmeldung fehlgeschlagen");
      router.replace(next);
      router.refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  if (!status) {
    return <p className="text-sm text-muted">Lade…</p>;
  }

  return (
    <Card className="w-full max-w-sm">
      <CardContent className="space-y-4 p-6">
        <div className="space-y-1 text-center">
          <div className="mx-auto flex h-11 w-11 items-center justify-center rounded-xl bg-primary/15 text-primary">
            <ShieldCheck size={22} />
          </div>
          <h1 className="text-lg font-bold text-fg">OMR Dashboard</h1>
          <p className="text-xs text-muted">Bitte anmelden, um fortzufahren.</p>
        </div>

        <form onSubmit={submit} className="space-y-3">
          <div>
            <Label htmlFor="u">Benutzer</Label>
            <Input id="u" autoComplete="username" value={username}
              onChange={(e) => setUsername(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="p">Passwort</Label>
            <Input id="p" type="password" autoComplete="current-password" autoFocus
              value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>
          {error && (
            <p className="rounded-lg bg-bad/10 px-3 py-2 text-xs text-bad">{error}</p>
          )}
          <Button type="submit" className="w-full" disabled={busy || !password}>
            <LogIn size={15} /> {busy ? "Anmelden…" : "Anmelden"}
          </Button>
        </form>

        <p className="text-center text-xs text-muted">
          Das Passwort ist das Dashboard-Passwort aus der <code>.env</code>
          {" "}(<code>DASHBOARD_PASS</code>) — ersatzweise der Server-Schlüssel.
        </p>
      </CardContent>
    </Card>
  );
}

export default function LoginPage() {
  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <Suspense fallback={<p className="text-sm text-muted">Lade…</p>}>
        <LoginForm />
      </Suspense>
    </div>
  );
}
