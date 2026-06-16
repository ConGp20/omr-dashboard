"use client";
import React, { useEffect, useMemo, useState } from "react";
import ReactFlow, {
  Background,
  Controls,
  type Edge,
  type Node,
  MarkerType,
} from "reactflow";
import "reactflow/dist/style.css";
import { useRouter } from "next/navigation";
import { nodeTypes } from "./TopologyNodes";
import { api } from "@/lib/api";
import { useDashboardStore } from "@/lib/store";
import type { Topology } from "@/lib/types";

// Column positions per node type for a clean left-to-right pipeline layout.
const COLUMN_X: Record<string, number> = {
  wan: 0,
  router: 280,
  vps: 560,
  exit: 820,
  internet: 1080,
  portforward: 820,
};

const EDGE_COLOR = "rgb(100 116 139)";

// Reference capacity (bps) an edge's line thickness scales against — same
// ballpark as LinkCard's CAP table, just one shared number since edges mix
// link/tunnel/portforward traffic.
const MAX_BPS_REF = 100e6;

function edgeWidth(bps: number): number {
  if (!bps) return 1.5;
  const ratio = Math.min(1, bps / MAX_BPS_REF);
  return 1.5 + ratio * 4.5; // idle 1.5px up to 6px at/above reference capacity
}

function edgeColor(bps: number): string {
  return bps > 0 ? "rgb(var(--primary))" : EDGE_COLOR;
}

function layout(topo: Topology): { nodes: Node[]; edges: Edge[] } {
  const byType: Record<string, typeof topo.nodes> = {};
  for (const n of topo.nodes) (byType[n.type] ??= []).push(n);

  const nodes: Node[] = [];
  for (const [type, group] of Object.entries(byType)) {
    const x = COLUMN_X[type] ?? 560;
    const count = group.length;
    group.forEach((n, i) => {
      // Center each column vertically; portforwards stack below the VPS row.
      const baseY = type === "portforward" ? 200 : 0;
      const spacing = type === "portforward" ? 70 : 110;
      const y = baseY + (i - (count - 1) / 2) * spacing;
      nodes.push({
        id: n.id,
        type: n.type,
        position: { x, y },
        data: n,
      });
    });
  }

  const edges: Edge[] = topo.edges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    animated: e.animated,
    label: e.label ?? undefined,
    // Thicker, brighter line the more traffic an edge is currently carrying.
    style: { stroke: edgeColor(e.bps), strokeWidth: edgeWidth(e.bps) },
    labelStyle: { fill: "rgb(var(--muted))", fontSize: 11 },
    labelBgStyle: { fill: "rgb(var(--surface))" },
    markerEnd: { type: MarkerType.ArrowClosed, color: edgeColor(e.bps) },
  }));

  return { nodes, edges };
}

export function TopologyDiagram() {
  const router = useRouter();
  const status = useDashboardStore((s) => s.status);
  const [topo, setTopo] = useState<Topology | null>(null);

  // Refetch topology whenever the high-level status changes (links up/down,
  // protocol switch, port-forward edits all alter the graph).
  useEffect(() => {
    api.get<Topology>("/dashboard/topology").then(setTopo).catch(() => {});
  }, [status?.state, status?.active_links, status?.exit_vpn]);

  const { nodes, edges } = useMemo(
    () => (topo ? layout(topo) : { nodes: [], edges: [] }),
    [topo],
  );

  const onNodeClick = (_evt: React.MouseEvent, node: Node) => {
    const target: Record<string, string> = {
      wan: "/links",
      router: "/links",
      vps: "/vps",
      exit: "/vps",
      portforward: "/vps",
      internet: "/vps",
    };
    const href = target[node.type as string];
    if (href) router.push(href);
  };

  return (
    <div data-tour-step="topology" className="h-[360px] w-full overflow-hidden rounded-xl border border-border bg-surface">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={onNodeClick}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        proOptions={{ hideAttribution: true }}
        nodesDraggable={false}
        nodesConnectable={false}
        zoomOnScroll={false}
        panOnScroll
      >
        <Background color="rgb(100 116 139 / 0.2)" gap={20} />
        <Controls showInteractive={false} className="!border-border" />
      </ReactFlow>
    </div>
  );
}
