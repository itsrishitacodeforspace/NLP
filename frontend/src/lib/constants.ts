import type { PartySide, ObligationType, RiskSeverity } from '@/types';

export const CONTRACT_TYPES = ['MSA', 'NDA', 'SPA', 'Employment', 'Vendor', 'Lease', 'Service', 'Other'] as const;
export type ContractTypeValue = (typeof CONTRACT_TYPES)[number];

export const PARTY_SIDES: PartySide[] = [
  'Provider',
  'Customer',
  'Employer',
  'Employee',
  'Vendor',
  'Buyer',
  'Seller',
  'Neutral',
];

export const OBLIGATION_TYPES: ObligationType[] = ['obligation', 'right', 'prohibition', 'condition'];

export const SEVERITIES: RiskSeverity[] = ['critical', 'high', 'medium', 'low'];

/** File extensions the backend accepts (routes_contracts._ALLOWED_EXT). */
export const ACCEPTED_EXTENSIONS = ['.pdf', '.docx', '.txt', '.md'];
export const ACCEPTED_MIME = 'application/pdf,.docx,text/plain,text/markdown';

export function hasAcceptedExtension(name: string): boolean {
  const lower = name.toLowerCase();
  return ACCEPTED_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

export function fileExtensionLabel(name: string): string {
  const i = name.lastIndexOf('.');
  return i === -1 ? '' : name.slice(i).toLowerCase();
}
