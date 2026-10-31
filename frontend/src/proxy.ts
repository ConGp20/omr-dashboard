// Server-side login gate (Next 16 "proxy", formerly middleware).
//
// Without it, an unauthenticated visitor gets the dashboard shell rendered, its
// panels fire their API calls, each comes back 401, and only then does the
// client redirect to /login — a visible flash plus a burst of failed requests
// as the first thing every user sees. Redirecting here means pages only render
// for someone who can actually use them.
import { NextRequest, NextResponse } from "next/server";
import { BACKEND, SESSION_COOKIE } from "@/lib/backend";

// Whether a login is needed at all is a backend decision (demo mode and a
// passwordless fresh install need none). Cache it briefly so ordinary
// navigation doesn't pay a backend round-trip on every page.
let cached: { required: boolean; at: number } | null = null;
const CACHE_MS = 10_000;

async function authRequired(): Promise<boolean | null> {
  if (cached && Date.now() - cached.at < CACHE_MS) return cached.required;
  try {
    const res = await fetch(`${BACKEND}/auth/status`, { cache: "no-store" });
    if (!res.ok) return null;
    const required = Boolean((await res.json()).auth_required);
    cached = { required, at: Date.now() };
    return required;
  } catch {
    return null;
  }
}

export default async function proxy(req: NextRequest) {
  // A present cookie is checked for validity by the backend on every call; an
  // expired one still ends up on /login via the client's 401 handling.
  if (req.cookies.get(SESSION_COOKIE)?.value) return NextResponse.next();

  // Backend unreachable (null): let the page render and show its own error
  // rather than bouncing the user to a login that cannot succeed either.
  if ((await authRequired()) !== true) return NextResponse.next();

  const login = new URL("/login", req.nextUrl);
  login.searchParams.set("next", req.nextUrl.pathname);
  return NextResponse.redirect(login);
}

export const config = {
  // Everything except the API proxy (it answers 401 itself), Next internals,
  // static files, and the login page itself.
  matcher: ["/((?!api|_next/static|_next/image|icon.svg|favicon.ico|login).*)"],
};
