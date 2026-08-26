// Generic proxy: /api/<x>/<y> -> backend /<x>/<y>. Handles JSON, multipart
// uploads and binary downloads. The SSE stream has its own dedicated handler.
import { NextRequest } from "next/server";
import { proxy } from "@/lib/backend";

export const dynamic = "force-dynamic";

// Next 15+: route params are provided as a Promise.
async function handler(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  return proxy(req, "/" + path.join("/"));
}

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const DELETE = handler;
