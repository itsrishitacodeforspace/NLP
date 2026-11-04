'use client';

import * as React from 'react';
import { cn } from '@/lib/utils';
import { severityMeta, toSeverity } from '@/lib/severity';
import type { GraphNode, GraphEdge } from '@/types';
import { NODE_KINDS, RISK_SEVERITIES, type GraphFilters, type NodeKind, type RiskSeverityFilter } from '@/features/graph/graph-view';

interface Props {
  filters: GraphFilters;
  onChange: (next: GraphFilters) => void;
  visible: { nodes: number; edges: number };
  total: { nodes: number; edges: number };
}

function Toggle({ checked, label, onToggle }: { checked: boolean; label: React.ReactNode; onToggle: () => void }) {
  return (
    <label className="flex cursor-pointer select-none items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground">
      <input
        type="checkbox"
        checked={checked}
        onChange={onToggle}
        className="h-3.5 w-3.5 rounded border-input accent-primary"
      />
      {label}
    </label>
  );
}

export function GraphFilterBar({ filters, onChange, visible, total }: Props) {
  const kindOn = (k: NodeKind) => onChange({ ...filters, kinds: { ...filters.kinds, [k]: !filters.kinds[k] } });
  const sevOn = (s: RiskSeverityFilter) =>
    onChange({ ...filters, severities: { ...filters.severities, [s]: !filters.severities[s] } });

  const allOff = visible.nodes === 0 && total.nodes > 0;

  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Nodes</span>
        {NODE_KINDS.map((k) => (
          <Toggle key={k} checked={filters.kinds[k]} label={k} onToggle={() => kindOn(k)} />
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Risk severity</span>
        {RISK_SEVERITIES.map((s) => (
          <Toggle key={s} checked={filters.severities[s]} label={severityMeta(s).label} onToggle={() => sevOn(s)} />
        ))}
      </div>

      <input
        type="search"
        value={filters.search}
        onChange={(e) => onChange({ ...filters, search: e.target.value })}
        placeholder="Search id / label / properties…"
        className="h-7 w-52 rounded-md border border-input bg-background px-2 text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      />

      <span className={cn('ml-auto text-xs text-muted-foreground', allOff && 'text-destructive')}>
        {visible.nodes}/{total.nodes} nodes · {visible.edges}/{total.edges} edges
      </span>
    </div>
  );
}

interface DetailRow {
  key: string;
  value: React.ReactNode;
}

function renderValue(v: unknown): React.ReactNode {
  if (v === null || v === undefined) return <span className="text-muted-foreground/60">null</span>;
  if (typeof v === 'string') return v;
  if (typeof v === 'number' || typeof v === 'boolean') return String(v);
  if (Array.isArray(v)) {
    if (v.length === 0) return '[]';
    if (v.every((x) => typeof x === 'string' || typeof x === 'number')) return v.join(', ');
    return JSON.stringify(v);
  }
  return JSON.stringify(v);
}

/** Side panel: all properties of the clicked node (or edge), formatted key/value. */
export function GraphDetailPanel({ node, edge }: { node?: GraphNode; edge?: GraphEdge }) {
  if (!node && !edge) {
    return (
      <div className="p-4 text-xs text-muted-foreground">
        Click a node (or an edge) to inspect its id, label and full properties here.
      </div>
    );
  }

  if (node) {
    const sev =
      node.label === 'Risk' && typeof node.properties?.severity === 'string' ? toSeverity(node.properties.severity) : null;
    return (
      <div className="space-y-3 p-4">
        <div className="flex items-start justify-between gap-2">
          <div>
            <p className="text-sm font-semibold">{node.label}</p>
            <p className="mt-0.5 break-all font-mono text-[11px] text-muted-foreground">{node.id}</p>
          </div>
          {sev ? (
            <span className={cn('rounded-full border px-2 py-0.5 text-[11px] font-medium', severityMeta(sev).bg, severityMeta(sev).text, severityMeta(sev).border)}>
              {severityMeta(sev).label}
            </span>
          ) : null}
        </div>
        <dl className="space-y-1.5">
          {Object.entries(node.properties ?? {}).map(([k, v]) => (
            <div key={k} className="grid grid-cols-[90px_1fr] gap-2 text-xs">
              <dt className="font-mono text-muted-foreground">{k}</dt>
              <dd className="break-words">{renderValue(v)}</dd>
            </div>
          ))}
          {Object.keys(node.properties ?? {}).length === 0 ? <p className="text-xs text-muted-foreground">No properties.</p> : null}
        </dl>
      </div>
    );
  }

  const e = edge as GraphEdge;
  return (
    <div className="space-y-3 p-4">
      <p className="text-sm font-semibold">Edge</p>
      <dl className="space-y-1.5 text-xs">
        <div className="grid grid-cols-[90px_1fr] gap-2">
          <dt className="font-mono text-muted-foreground">type</dt>
          <dd>{e.type}</dd>
        </div>
        <div className="grid grid-cols-[90px_1fr] gap-2">
          <dt className="font-mono text-muted-foreground">source</dt>
          <dd className="break-all font-mono">{e.source}</dd>
        </div>
        <div className="grid grid-cols-[90px_1fr] gap-2">
          <dt className="font-mono text-muted-foreground">target</dt>
          <dd className="break-all font-mono">{e.target}</dd>
        </div>
      </dl>
    </div>
  );
}
