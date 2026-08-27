// Login handler. Exchanges credentials for a backend JWT and stores it in an
// httpOnly cookie, so the token is never readable by browser JavaScript — the
// proxy attaches it server-side on every subsequent call.
//
// This static route takes precedence over the /api/[...path] catch-all.
import { NextRequest, NextResponse } from "next/server";
import { BACKEND, SESSION_COOKIE } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ detail: "Ungültige Anfrage" }, { status: 400 });
  }

  let res: Response;
  try {
    res = await fetch(`${BACKEND}/auth/login`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    });
  } catch (err) {
    return NextResponse.json(
      { detail: `Backend nicht erreichbar: ${(err as Error).message}` },
      { status: 502 },
    );
  }

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    return NextResponse.json(
      { detail: data.detail ?? "Anmeldung fehlgeschlagen" },
      { status: res.status },
    );
  }

  const out = NextResponse.json({ success: true });
  out.cookies.set(SESSION_COOKIE, data.access_token, {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    // The dashboard is reached over http on the management tunnel, so this
    // cannot be hard-coded to secure; honour HTTPS when it is in use.
    secure: req.nextUrl.protocol === "https:",
    maxAge: 60 * 60 * 12,
  });
  return out;
}
