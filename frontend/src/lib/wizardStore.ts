import { create } from "zustand";
import type { WizardWan } from "./types";

interface WizardState {
  step: number;
  // collected data
  vpsIp: string;
  omrKey: string;
  vpsVersion?: string;
  protocolsAvailable: string[];
  routerIp: string;
  routerUser: string;
  routerPass: string;
  wans: WizardWan[];
  protocol: string;
  lanIp: string;
  dhcpRange: string;
  set: (patch: Partial<WizardState>) => void;
  next: () => void;
  back: () => void;
  reset: () => void;
}

const initial = {
  step: 0,
  vpsIp: "",
  omrKey: "",
  vpsVersion: undefined,
  protocolsAvailable: [] as string[],
  routerIp: "192.168.100.1",
  routerUser: "root",
  routerPass: "",
  wans: [] as WizardWan[],
  protocol: "glorytun_tcp",
  lanIp: "192.168.100.1",
  dhcpRange: "192.168.100.100-200",
};

export const useWizard = create<WizardState>((set) => ({
  ...initial,
  set: (patch) => set(patch),
  next: () => set((s) => ({ step: s.step + 1 })),
  back: () => set((s) => ({ step: Math.max(0, s.step - 1) })),
  reset: () => set(initial),
}));
