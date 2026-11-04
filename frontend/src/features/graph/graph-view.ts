'use client';

import type { Node, Edge } from '@xyflow/react';
import { MarkerType } from '@xyflow/react';
import type { GraphNode, GraphSnapshot } from '@/types';
import { severityMeta, toSeverity } from '@/lib/severity';

export type NodeKind = 'Contract' | 'Clause' | 'Obligation' | 'Risk' | 'Party';
export const NODE_KINDS: NodeKind[] = ['Contract', 'Clause', 'Obligation', 'Risk', 'Party'];

export type RiskSeverityFilter = 'critical' | 'high' | 'medium' | 'low';
export const RISK_SEVERITIES: RiskSeverityFilter[] = ['critical', 'high', 'medium', 'low'];

export interface GraphFilters {
  kinds: Record<NodeKind, boolean>;
  severities: Record<RiskSeverityFilter, boolean>;
  search: string;
}

export const defaultFilters: GraphFilters = {
  kinds: { Contract: true, Clause: true, Obligation: true, Risk: true, Party: true },
  severities: { critical: true, high: true, medium: true, low: true },
  search: '',
};

/** True when the node passes all active filters. Unknown labels are treated as Clause. */
export function nodeMatchesFilters(node: GraphNode, f: GraphFilters): boolean {
  const kind: NodeKind = (NODE_KINDS as string[]).includes(node.label) ? (node.label as NodeKind) : 'Clause';
  if (!f.kinds[kind]) return false;

  if (kind === 'Risk') {
    const sev = toSeverity(typeof node.properties?.severity === 'string' ? node.properties.severity : undefined);
    if (sev !== 'informational' && !f.severities[sev]) return false;
  }

  const q = f.search.trim().toLowerCase();
  if (q) {
    const haystack = [node.id, node.label, JSON.stringify(node.properties ?? {})]
      .join('\n')
      .toLowerCase();
    if (!haystack.includes(q)) return false;
  }

  return true;
}

/** Subset of nodes/edges that pass the filters (edges need both endpoints visible). */
export function applyFilters(snapshot: GraphSnapshot, f: GraphFilters): { nodes: GraphNode[]; edges: GraphEdgeLike[] } {
  const kept = new Set(snapshot.nodes.filter((n) => nodeMatchesFilters(n, f)).map((n) => n.id));
  const nodes = snapshot.nodes.filter((n) => kept.has(n.id));
  const edges = snapshot.edges.filter((e) => kept.has(e.source) && kept.has(e.target));
  return { nodes, edges };
}

type GraphEdgeLike = GraphSnapshot['edges'][number];

/** Tailwind-ish styling per node label. Restrained: borders + a small label chip. */
export function nodeClassName(label: string, properties: GraphNode['properties']): string {
  switch (label) {
    case 'Contract':
      return 'rounded-lg border-2 border-primary bg-card text-sm font-semibold';
    case 'Obligation':
      return 'rounded-md border border-secondary bg-secondary/60 text-sm';
    case 'Risk': {
      const sev = toSeverity(typeof properties?.severity === 'string' ? properties.severity : undefined);
      const hex = severityMeta(sev).hex;
      return `rounded-md border-2 bg-card text-sm [border-color:${hex}]`;
    }
    default:
      return 'rounded-md border bg-card text-sm';
  }
}

/** Short one-line summary of the node's properties shown inside the node. */
export function nodeSummary(label: string, properties: GraphNode['properties']): string {
  const p = properties ?? {};
  const first = (k: string): string | undefined => {
    const v = p[k];
    if (typeof v === 'string') return v;
    if (typeof v === 'number') return String(v);
    return undefined;
  };
  if (label === 'Contract') return [first('title'), first('risk_level') ? `risk: ${first('risk_level')}` : undefined].filter(Boolean).join(' · ');
  if (label === 'Clause') {
    const types = Array.isArray(p.clause_types) ? (p.clause_types as string[]).join(', ') : undefined;
    return [truncate(first('heading'), 48), types].filter(Boolean).join(' · ');
  }
  if (label === 'Obligation') return [p.type, first('action') ? `→ ${first('action')}` : undefined].filter(Boolean).join(' ');
  if (label === 'Risk') return [first('name'), first('severity') ? `(${first('severity')})` : undefined].filter(Boolean).join(' ');
  if (label === 'Party') return first('name') ?? '';
  return '';
}

function truncate(s: string | undefined, n: number): string | undefined {
  if (!s) return undefined;
  return s.length > n ? `${s.slice(0, n - 1)}…` : s;
}

/**
 * Tidy top-down tree layout. The backend returns no positions, so this is the
 * sole layout authority: parents sit centred over their children and leaves are
 * spaced evenly — instead of everything stacking at the origin (0,0).
 */
function computeLayout(
  nodes: GraphNode[],
  edges: GraphSnapshot['edges']
): Map<string, { x: number; y: number }> {
  const pos = new Map<string, { x: number; y: number }>();
  const idSet = new Set(nodes.map((n) => n.id));

  const children = new Map<string, string[]>();
  const hasParent = new Set<string>();
  for (const e of edges) {
    if (!idSet.has(e.source) || !idSet.has(e.target)) continue;
    if (!children.has(e.source)) children.set(e.source, []);
    children.get(e.source)!.push(e.target);
    hasParent.add(e.target);
  }

  const X_GAP = 260; // >= NodeCard max width so siblings don't overlap
  const Y_GAP = 170;
  let leafCursor = 0;
  const visited = new Set<string>();

  const dfs = (id: string, depth: number): number => {
    if (visited.has(id)) return leafCursor * X_GAP; // multi-parent / cycle guard
    visited.add(id);
    const kids = (children.get(id) ?? []).filter((k) => idSet.has(k));
    if (kids.length === 0) {
      const x = leafCursor * X_GAP;
      leafCursor += 1;
      pos.set(id, { x, y: depth * Y_GAP });
      return x;
    }
    const xs = kids.map((k) => dfs(k, depth + 1));
    const center = (Math.min(...xs) + Math.max(...xs)) / 2;
    pos.set(id, { x: center, y: depth * Y_GAP });
    return center;
  };

  // Roots = nodes with no incoming edge (the Contract + any contract-level risk).
  for (const n of nodes) if (!hasParent.has(n.id)) dfs(n.id, 0);
  // Unreachable stragglers (defensive) — line them up on the top row.
  for (const n of nodes) {
    if (!pos.has(n.id)) {
      pos.set(n.id, { x: leafCursor * X_GAP, y: 0 });
      leafCursor += 1;
    }
  }
  return pos;
}

/**
 * Map the (already filtered) subset of a backend snapshot onto React Flow
 * nodes/edges. Pure — renders exactly what the backend returned, nothing invented.
 */
export function toFlow(snapshot: GraphSnapshot, subset: { nodes: GraphNode[]; edges: GraphSnapshot['edges'] }): { nodes: Node[]; edges: Edge[] } {
  const positions = computeLayout(subset.nodes, subset.edges);
  const nodes: Node[] = subset.nodes.map((n) => ({
    id: n.id,
    type: 'card',
    position: positions.get(n.id) ?? { x: 0, y: 0 },
    data: { label: n.label, summary: nodeSummary(n.label, n.properties), node: n },
    className: nodeClassName(n.label, n.properties),
  }));

  const edges: Edge[] = subset.edges.map((e, i) => ({
    id: `${snapshot.contract_id}:${e.source}->${e.target}:${e.type}:${i}`,
    source: e.source,
    target: e.target,
    label: e.type,
    type: 'default',
    animated: false,
    markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16, color: '#94a3b8' },
    style: { stroke: '#94a3b8', strokeWidth: 1.25 },
    labelStyle: { fill: '#64748b', fontSize: 10 },
    labelBgStyle: { fill: 'transparent', fillOpacity: 0 },
    className: 'graph-edge',
  }));

  return { nodes, edges };
}
