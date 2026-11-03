'use client';

import * as React from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  BackgroundVariant,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { toFlow, applyFilters, defaultFilters, type GraphFilters } from '@/features/graph/graph-view';
import { GraphFilterBar, GraphDetailPanel } from '@/components/graph/graph-filter-bar';
import { Card } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { EmptyState } from '@/components/ui/state';
import type { GraphNode, GraphSnapshot } from '@/types';

interface Props {
  snapshot?: GraphSnapshot;
  isLoading?: boolean;
  /** Render only the loading skeleton (contract list still loading, nothing to diff yet). */
  skeletonOnly?: boolean;
}

function NodeCard({ data }: { data: { label: string; summary: string; node: GraphNode } }) {
  return (
    <div className="min-w-[160px] max-w-[260px]">
      <div className="mb-1">
        <span className="rounded bg-secondary px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-secondary-foreground">
          {data.label}
        </span>
      </div>
      <p className="text-xs leading-snug">{data.summary || '(no summary)'}</p>
    </div>
  );
}

const nodeTypes = { card: NodeCard };

export function GraphCanvas({ snapshot, isLoading = false, skeletonOnly = false }: Props) {
  const [filters, setFilters] = React.useState<GraphFilters>(defaultFilters);
  const [selectedNode, setSelectedNode] = React.useState<GraphNode | null>(null);
  const [selectedEdge, setSelectedEdge] = React.useState<GraphSnapshot['edges'][number] | null>(null);

  const filtered = React.useMemo(
    () => (snapshot ? applyFilters(snapshot, filters) : { nodes: [], edges: [] }),
    [snapshot, filters]
  );

  // Base layout state; positions are computed client-side by fitView/elbow defaults.
  const [baseNodes, setBaseNodes, onNodesChange] = useNodesState<Node>([]);
  const [baseEdges, setBaseEdges, onEdgesChange] = useEdgesState<Edge>([]);

  React.useEffect(() => {
    if (!snapshot) {
      setBaseNodes([]);
      setBaseEdges([]);
      return;
    }
    const { nodes, edges } = toFlow(snapshot, filtered);
    setBaseNodes(nodes);
    setBaseEdges(edges);
  }, [snapshot, filtered, setBaseNodes, setBaseEdges]);

  React.useEffect(() => {
    setSelectedNode(null);
    setSelectedEdge(null);
  }, [snapshot?.contract_id]);

  if (skeletonOnly || isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-[420px] w-full" />
      </div>
    );
  }

  if (!snapshot || snapshot.nodes.length === 0) {
    return (
      <EmptyState
        title="No graph available for this contract"
        description="The backend returned no nodes/edges for this contract. Relationships are only shown when the backend produces them — nothing here is inferred."
      />
    );
  }

  const onNodeClick = (_: React.MouseEvent, n: Node) => {
    const node = (n.data as { node?: GraphNode } | undefined)?.node ?? null;
    setSelectedEdge(null);
    setSelectedNode(node);
  };

  const onEdgeClick = (_: React.MouseEvent, e: Edge) => {
    const src = e.source;
    const tgt = e.target;
    const match = snapshot.edges.find((x) => x.source === src && x.target === tgt && x.type === (e.label as string));
    setSelectedNode(null);
    setSelectedEdge(match ?? null);
  };

  return (
    <div className="space-y-3">
      <Card className="p-3">
        <GraphFilterBar
          filters={filters}
          onChange={setFilters}
          visible={{ nodes: filtered.nodes.length, edges: filtered.edges.length }}
          total={{ nodes: snapshot.nodes.length, edges: snapshot.edges.length }}
        />
      </Card>

      <div className="grid gap-3 lg:grid-cols-[1fr_320px]">
        <Card className="overflow-hidden">
          <div className="h-[520px] w-full">
            <ReactFlow
              nodes={baseNodes}
              edges={baseEdges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              nodeTypes={nodeTypes}
              fitView
              fitViewOptions={{ padding: 0.25, maxZoom: 1 }}
              minZoom={0.15}
              maxZoom={2}
              onNodeClick={onNodeClick}
              onEdgeClick={onEdgeClick}
              nodesConnectable={false}
              deleteKeyCode={null}
            >
              <Background variant={BackgroundVariant.Dots} gap={18} size={1} />
              <Controls position="bottom-left" showInteractive={false} />
              <MiniMap position="bottom-right" pannable zoomable nodeStrokeWidth={2} />
            </ReactFlow>
          </div>
        </Card>

        <Card>
          <div className="border-b px-4 py-2.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Details
          </div>
          <div className="max-h-[520px] overflow-y-auto">
            <GraphDetailPanel node={selectedNode ?? undefined} edge={selectedEdge ?? undefined} />
          </div>
        </Card>
      </div>
    </div>
  );
}
