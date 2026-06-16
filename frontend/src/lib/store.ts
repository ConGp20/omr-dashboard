import { create } from "zustand";
import type { DashboardStatus } from "./types";

// How many recent rx_bps samples to keep per link for the LinkCard sparkline.
// At the ~10s push interval this covers a few minutes of trend.
const HISTORY_LENGTH = 20;

interface DashboardState {
  status: DashboardStatus | null;
  connected: boolean;
  linkHistory: Record<string, number[]>;
  setStatus: (s: DashboardStatus) => void;
  setConnected: (c: boolean) => void;
}

export const useDashboardStore = create<DashboardState>((set, get) => ({
  status: null,
  connected: false,
  linkHistory: {},
  setStatus: (status) => {
    const prev = get().linkHistory;
    const next: Record<string, number[]> = {};
    for (const link of status.links) {
      const series = prev[link.id] ?? [];
      next[link.id] = [...series, link.rx_bps].slice(-HISTORY_LENGTH);
    }
    set({ status, linkHistory: next });
  },
  setConnected: (connected) => set({ connected }),
}));
