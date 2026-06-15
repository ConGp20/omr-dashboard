import { Cable, Radio, Satellite, Wifi, Network, Phone } from "lucide-react";
import type { LinkType } from "@/lib/types";

const MAP: Record<LinkType, typeof Cable> = {
  fiber: Network,
  dsl: Phone,
  lte: Radio,
  "5g": Wifi,
  ethernet: Cable,
  satellite: Satellite,
  other: Cable,
};

export function LinkIcon({ type, size = 18 }: { type: LinkType; size?: number }) {
  const Icon = MAP[type] ?? Cable;
  return <Icon size={size} />;
}
