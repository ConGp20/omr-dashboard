// Dedicated SSE proxy: streams the backend /dashboard/stream to the browser.
// Uses a push-based ReadableStream (continuous read loop in start) which is the
// reliable pattern for proxying event streams through Next.js route handlers.
import { NextRequest } from "next/server";
import { BACKEND } from "@/lib/backend";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";
export const fetchCache = "force-no-store";

export async function GET(req: NextRequest) {
  let upstream: Response;
  try {
    upstream = await fetch(`${BACKEND}/dashboard/stream`, {
      headers: { Accept: "text/event-stream" },
      cache: "no-store",
    });
  } catch {
    return new Response("event: error\ndata: {}\n\n", {
      status: 502,
      headers: { "Content-Type": "text/event-stream" },
    });
  }

  if (!upstream.body) {
    return new Response("event: error\ndata: {}\n\n", {
      status: 502,
      headers: { "Content-Type": "text/event-stream" },
    });
  }
  const reader = upstream.body.getReader();

  const stream = new ReadableStream({
    async start(controller) {
      const onAbort = () => {
        reader.cancel().catch(() => {});
      };
      req.signal.addEventListener("abort", onAbort);
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          controller.enqueue(value);
        }
      } catch {
        /* upstream closed */
      } finally {
        req.signal.removeEventListener("abort", onAbort);
        controller.close();
      }
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
