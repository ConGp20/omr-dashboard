import { Handle, Position } from "reactflow";
import {
  Router,
  Server,
  Globe,
  Lock,
  ArrowRightLeft,
  Shield,
} from "lucide-react";
import { LinkIcon } from "@/components/LinkIcon";
import { formatBps, cn } from "@/lib/utils";
import type { LinkType } from "@/lib/types";

const STATE_RING = {
  up: "ring-good/50 border-good/40",
  degraded: "ring-warn/50 border-warn/40",
  down: "ring-bad/50 border-bad/40",
};

const OWNER_BADGE: Record<string, { label: string; cls: string }> = {
  router: { label: "🖥️ Router", cls: "bg-blue-500/15 text-blue-400" },
  vps: { label: "☁️ VPS", cls: "bg-purple-500/15 text-purple-400" },
  sync: { label: "🔄 Sync", cls: "bg-amber-500/15 text-amber-400" },
};

function Shell({
  children,
  state = "up",
  className,
}: {
  children: React.ReactNode;
  state?: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "min-w-[120px] rounded-xl border bg-surface p-3 shadow-md ring-2",
        STATE_RING[state as keyof typeof STATE_RING] ?? STATE_RING.up,
        className,
      )}
    >
      {children}
    </div>
  );
}

function OwnerBadge({ owner }: { owner?: string | null }) {
  if (!owner || !OWNER_BADGE[owner]) return null;
  const b = OWNER_BADGE[owner];
  return (
    <span className={cn("mt-1 inline-block rounded px-1.5 py-0.5 text-[10px] font-medium", b.cls)}>
      {b.label}
    </span>
  );
}

export function WanNode({ data }: { data: any }) {
  const d = data.detail ?? {};
  return (
    <Shell state={data.state}>
      <Handle type="source" position={Position.Right} className="!bg-muted" />
      <div className="flex items-center gap-2">
        <LinkIcon type={(d.type as LinkType) ?? "other"} size={16} />
        <span className="text-sm font-semibold text-fg">{data.label}</span>
      </div>
      {data.state !== "down" && (
        <div className="mt-1 text-[11px] text-muted">
          ↓ {formatBps(d.rx_bps ?? 0)} · {d.latency_ms ?? "—"}ms
        </div>
      )}
      <OwnerBadge owner={data.owner} />
    </Shell>
  );
}

export function RouterNode({ data }: { data: any }) {
  return (
    <Shell state={data.state} className="bg-surface-2">
      <Handle type="target" position={Position.Left} className="!bg-muted" />
      <Handle type="source" position={Position.Right} className="!bg-muted" />
      <div className="flex items-center gap-2">
        <Router size={18} className="text-primary" />
        <span className="text-sm font-semibold text-fg">{data.label}</span>
      </div>
      <div className="mt-1 text-[11px] text-muted">MPTCP-Peer</div>
      <OwnerBadge owner={data.owner} />
    </Shell>
  );
}

export function VpsNode({ data }: { data: any }) {
  const d = data.detail ?? {};
  return (
    <Shell state={data.state} className="bg-surface-2">
      <Handle type="target" position={Position.Left} className="!bg-muted" />
      <Handle type="source" position={Position.Right} className="!bg-muted" />
      <div className="flex items-center gap-2">
        <Server size={18} className="text-purple-400" />
        <span className="text-sm font-semibold text-fg">{data.label}</span>
      </div>
      {d.public_ip && <div className="mt-1 text-[11px] text-muted">{d.public_ip}</div>}
      <div className="mt-1 flex items-center gap-1 text-[11px] text-muted">
        <Lock size={10} /> {d.protocol ?? "?"}
      </div>
      <OwnerBadge owner={data.owner} />
    </Shell>
  );
}

export function InternetNode({ data }: { data: any }) {
  return (
    <Shell state={data.state}>
      <Handle type="target" position={Position.Left} className="!bg-muted" />
      <div className="flex items-center gap-2">
        <Globe size={18} className="text-good" />
        <span className="text-sm font-semibold text-fg">{data.label}</span>
      </div>
    </Shell>
  );
}

export function ExitNode({ data }: { data: any }) {
  return (
    <Shell state={data.state}>
      <Handle type="target" position={Position.Left} className="!bg-muted" />
      <Handle type="source" position={Position.Right} className="!bg-muted" />
      <div className="flex items-center gap-2">
        <Shield size={18} className="text-amber-400" />
        <span className="text-sm font-semibold text-fg">{data.label}</span>
      </div>
      <div className="mt-1 text-[11px] text-muted">Exit-VPN</div>
      <OwnerBadge owner={data.owner} />
    </Shell>
  );
}

export function PortForwardNode({ data }: { data: any }) {
  const d = data.detail ?? {};
  return (
    <Shell state={data.state} className="min-w-[140px]">
      <Handle type="target" position={Position.Left} className="!bg-muted" />
      <div className="flex items-center gap-2">
        <ArrowRightLeft size={15} className="text-primary" />
        <span className="text-xs font-semibold text-fg">{data.label}</span>
      </div>
      {d.dest && <div className="mt-1 text-[10px] text-muted">→ {String(d.dest)} ({String(d.proto)})</div>}
      <OwnerBadge owner={data.owner} />
    </Shell>
  );
}

export const nodeTypes = {
  wan: WanNode,
  router: RouterNode,
  vps: VpsNode,
  internet: InternetNode,
  exit: ExitNode,
  portforward: PortForwardNode,
};
