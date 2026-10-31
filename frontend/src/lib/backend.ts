// Server-side helper used by Next.js route handlers to reach the backend
// sidecar. Centralises the base URL and passes bodies/headers through verbatim
// so it works for JSON, multipart uploads and binary downloads alike.
import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.BACKEND_URL || "http://127.0.0.1:8000";

/** Name of the httpOnly cookie holding the backend session token. */
export const SESSION_COOKIE = "omr_session";

/**
 * Authorization header for the backend, taken from the session cookie.
 *
 * The token lives in an httpOnly cookie, so it is attached here on the server
 * and never becomes readable by browser JavaScript — the same reason the admin
 * key never leaves this process.
 */
export function authHeaders(req: NextRequest): Record<string, string> {
  const token = req.cookies.get(SESSION_COOKIE)?.value;
  return token ? { authorization: `Bearer ${token}` } : {};
}

export async function proxy(
  req: NextRequest,
  backendPath: string,
): Promise<NextResponse> {
  const search = req.nextUrl.search || "";
  const url = `${BACKEND}${backendPath}${search}`;

  const init: RequestInit = { method: req.method, headers: { ...authHeaders(req) } };
  const ct = req.headers.get("content-type");
  if (ct) (init.headers as Record<string, string>)["content-type"] = ct;

  if (req.method !== "GET" && req.method !== "DELETE" && req.method !== "HEAD") {
    init.body = Buffer.from(await req.arrayBuffer());
  }

  try {
    const res = await fetch(url, init);
    const buf = Buffer.from(await res.arrayBuffer());
    const headers = new Headers();
    const passthrough = ["content-type", "content-disposition", "cache-control"];
    for (const h of passthrough) {
      const v = res.headers.get(h);
      if (v) headers.set(h, v);
    }
    return new NextResponse(buf, { status: res.status, headers });
  } catch (err) {
    return NextResponse.json(
      { detail: `Backend nicht erreichbar: ${(err as Error).message}` },
      { status: 502 },
    );
  }
}

export { BACKEND };
