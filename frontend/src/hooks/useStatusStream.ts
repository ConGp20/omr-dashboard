"use client";
import { useEffect } from "react";
import { useDashboardStore } from "@/lib/store";
import type { DashboardStatus } from "@/lib/types";

/**
 * Subscribe to the backend SSE stream (via the /api/stream proxy) and keep the
 * Zustand store updated with live status. Falls back to polling if the stream
 * cannot be established.
 */
export function useStatusStream() {
  const setStatus = useDashboardStore((s) => s.setStatus);
  const setConnected = useDashboardStore((s) => s.setConnected);

  useEffect(() => {
    let es: EventSource | null = null;
    let pollTimer: ReturnType<typeof setInterval> | null = null;
    let stopped = false;

    const startPolling = () => {
      if (pollTimer) return;
      const poll = async () => {
        try {
          const res = await fetch("/api/dashboard/status");
          if (res.ok) {
            setStatus((await res.json()) as DashboardStatus);
            setConnected(true);
          }
        } catch {
          setConnected(false);
        }
      };
      poll();
      pollTimer = setInterval(poll, 5000);
    };

    try {
      es = new EventSource("/api/stream");
      es.addEventListener("status", (e) => {
        setStatus(JSON.parse((e as MessageEvent).data) as DashboardStatus);
        setConnected(true);
      });
      es.onerror = () => {
        setConnected(false);
        es?.close();
        if (!stopped) startPolling();
      };
    } catch {
      startPolling();
    }

    return () => {
      stopped = true;
      es?.close();
      if (pollTimer) clearInterval(pollTimer);
    };
  }, [setStatus, setConnected]);
}
