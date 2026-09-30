import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Format bits/second into a human readable string (Mbps focused). */
export function formatBps(bps: number): string {
  if (!bps || bps < 1000) return "0 bps";
  const mbps = bps / 1e6;
  if (mbps >= 1000) return `${(mbps / 1000).toFixed(2)} Gbps`;
  if (mbps >= 1) return `${mbps.toFixed(1)} Mbps`;
  return `${(bps / 1000).toFixed(0)} kbps`;
}

export function mbps(bps: number): number {
  return bps / 1e6;
}

/** Format a byte count into GB/TB (decimal, as ISPs bill volume). */
export function formatBytes(bytes: number): string {
  if (!bytes || bytes < 1e6) return "0 MB";
  const gb = bytes / 1e9;
  if (gb >= 1000) return `${(gb / 1000).toFixed(2)} TB`;
  if (gb >= 1) return `${gb.toFixed(2)} GB`;
  return `${(bytes / 1e6).toFixed(0)} MB`;
}

const TYPE_LABELS: Record<string, string> = {
  fiber: "Glasfaser",
  dsl: "DSL",
  lte: "LTE",
  "5g": "5G",
  ethernet: "Ethernet",
  satellite: "Satellit",
  other: "Sonstige",
};
export function linkTypeLabel(t: string): string {
  return TYPE_LABELS[t] ?? t;
}

export function relativeTime(ts: number): string {
  const diff = Date.now() / 1000 - ts;
  if (diff < 60) return "gerade eben";
  if (diff < 3600) return `vor ${Math.floor(diff / 60)} Min`;
  if (diff < 86400) return `vor ${Math.floor(diff / 3600)} Std`;
  return `vor ${Math.floor(diff / 86400)} Tagen`;
}
