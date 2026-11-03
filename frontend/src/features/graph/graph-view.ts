'use client';

import type { Node, Edge } from '@xyflow/react';
import { MarkerType } from '@xyflow/react';
import type { GraphNode, GraphSnapshot } from '@/types';
import { severityMeta, toSeverity } from '@/lib/severity';

export type NodeKind = 'Contract' | 'Clause' | 'Obligation' | 'Risk';
export const NODE_KINDS: NodeKind[] = ['Contract', 'Clause', 'Obligation', 'Risk'];

export type RiskSeverityFilter = 'critical' | 'high' | 'medium' | 'low';
export const RISK_SEVERITIES: RiskSeverityFilter[] = ['critical', 'high', 'medium', 'low'];

export interface GraphFilters {
  kinds: Record<NodeKind, boolean>;
  severities: Record<RiskSeverityFilter, boolean>;
  search: string;
}

export const defaultFilters: GraphFilters = {
  kinds: { Contract: true, Clause: true, Obligation: true, Risk: true },
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
      return 'rounded-lg border-2 border-primary bg-card text-sm font-semibold shadow-sm';
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
  return '';
}

function truncate(s: string | undefined, n: number): string | undefined {
  if (!s) return undefined;
  return s.length > n ? `${s.slice(0, n - 1)}…` : s;
}

/**
 * Map the (already filtered) subset of a backend snapshot onto React Flow
 * nodes/edges. Pure — renders exactly what the backend returned, nothing invented.
 */
export function toFlow(snapshot: GraphSnapshot, subset: { nodes: GraphNode[]; edges: GraphSnapshot['edges'] }): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = subset.nodes.map((n) => ({
    id: n.id,
    position: { x: 0, y: 0 },
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
