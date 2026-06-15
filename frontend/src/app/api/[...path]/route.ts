// Generic proxy: /api/<x>/<y> -> backend /<x>/<y>. Handles JSON, multipart
// uploads and binary downloads. The SSE stream has its own dedicated handler.
import { NextRequest } from "next/server";
import { proxy } from "@/lib/backend";

export const dynamic = "force-dynamic";

function handler(req: NextRequest, ctx: { params: { path: string[] } }) {
  return proxy(req, "/" + ctx.params.path.join("/"));
}

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const DELETE = handler;
