// Clears the session cookie. Static route, so it wins over /api/[...path].
import { NextResponse } from "next/server";
import { SESSION_COOKIE } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function POST() {
  const out = NextResponse.json({ success: true });
  out.cookies.set(SESSION_COOKIE, "", { httpOnly: true, path: "/", maxAge: 0 });
  return out;
}
