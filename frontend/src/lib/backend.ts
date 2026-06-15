// Server-side helper used by Next.js route handlers to reach the backend
// sidecar. Centralises the base URL and passes bodies/headers through verbatim
// so it works for JSON, multipart uploads and binary downloads alike.
import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.BACKEND_URL || "http://127.0.0.1:8000";

export async function proxy(
  req: NextRequest,
  backendPath: string,
): Promise<NextResponse> {
  const search = req.nextUrl.search || "";
  const url = `${BACKEND}${backendPath}${search}`;

  const init: RequestInit = { method: req.method, headers: {} };
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
