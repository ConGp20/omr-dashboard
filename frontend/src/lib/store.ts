import { create } from "zustand";
import type { DashboardStatus } from "./types";

interface DashboardState {
  status: DashboardStatus | null;
  connected: boolean;
  setStatus: (s: DashboardStatus) => void;
  setConnected: (c: boolean) => void;
}

export const useDashboardStore = create<DashboardState>((set) => ({
  status: null,
  connected: false,
  setStatus: (status) => set({ status }),
  setConnected: (connected) => set({ connected }),
}));
