import type { components } from '@/types/api';

export type ContractSummary = components['schemas']['ContractSummary'];
export type Clause = components['schemas']['Clause'];
export type Obligation = components['schemas']['Obligation'];
export type RiskFlag = components['schemas']['RiskFlag'];
export type AnalysisResult = components['schemas']['AnalysisResult'];
export type JobInfo = components['schemas']['JobInfo'];
export type JobStatus = components['schemas']['JobStatus'];
export type RiskSeverity = components['schemas']['RiskSeverity'];
export type ContractType = components['schemas']['ContractType'];
export type PartySide = components['schemas']['PartySide'];
export type ObligationType = components['schemas']['ObligationType'];
export type TokenResponse = components['schemas']['TokenResponse'];
export type UserInfo = components['schemas']['UserInfo'];
export type CaseLawReference = components['schemas']['CaseLawReference'];
export type EvidenceSpan = components['schemas']['EvidenceSpan'];

export type GraphNode = { id: string; label: string; properties: Record<string, unknown> };
export type GraphEdge = { source: string; target: string; type: string; properties?: Record<string, unknown> };
export type GraphSnapshot = { contract_id: string; nodes: GraphNode[]; edges: GraphEdge[] };
