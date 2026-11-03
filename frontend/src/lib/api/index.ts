import { apiRequest } from './client';
import type {
  ContractSummary,
  Clause,
  Obligation,
  RiskFlag,
  JobInfo,
  TokenResponse,
  UserInfo,
  GraphSnapshot,
  ContractType,
  PartySide,
} from '@/types';

export interface UploadParams {
  file: File;
  contractType?: ContractType;
  userRole?: PartySide;
  jurisdiction?: string;
}

export const contractsApi = {
  /** Upload a contract and start background analysis. Returns the JobInfo. */
  upload({ file, contractType = 'Other', userRole = 'Customer', jurisdiction = 'India' }: UploadParams): Promise<JobInfo> {
    const fd = new FormData();
    fd.append('file', file);
    fd.append('contract_type', contractType);
    fd.append('user_role', userRole);
    fd.append('jurisdiction', jurisdiction);
    return apiRequest<JobInfo>('contracts/upload', { method: 'POST', formData: fd });
  },

  summary: (contractId: string, signal?: AbortSignal): Promise<ContractSummary> =>
    apiRequest<ContractSummary>(`contracts/${contractId}/summary`, { signal }),

  clauses: (contractId: string, signal?: AbortSignal): Promise<{ clauses: Clause[] }> =>
    apiRequest<{ clauses: Clause[] }>(`contracts/${contractId}/clauses`, { signal }),

  obligations: (contractId: string, signal?: AbortSignal): Promise<{ obligations: Obligation[] }> =>
    apiRequest<{ obligations: Obligation[] }>(`contracts/${contractId}/obligations`, { signal }),

  risks: (contractId: string, signal?: AbortSignal): Promise<{ risks: RiskFlag[] }> =>
    apiRequest<{ risks: RiskFlag[] }>(`contracts/${contractId}/risks`, { signal }),
};

export const jobsApi = {
  get: (jobId: string, signal?: AbortSignal): Promise<JobInfo> =>
    apiRequest<JobInfo>(`jobs/${jobId}`, { signal }),

  list: (signal?: AbortSignal): Promise<{ jobs: JobInfo[] }> =>
    apiRequest<{ jobs: JobInfo[] }>('jobs', { signal }),
};

export const graphApi = {
  get: (contractId: string, signal?: AbortSignal): Promise<GraphSnapshot> =>
    apiRequest<GraphSnapshot>(`graph/${contractId}`, { signal }),
};

export const authApi = {
  /** Exchange username/password for a bearer token. Throws 400 when auth is disabled. */
  login(username: string, password: string): Promise<TokenResponse> {
    const fd = new FormData();
    fd.append('username', username);
    fd.append('password', password);
    return apiRequest<TokenResponse>('auth/token', { method: 'POST', formData: fd, noAuth: true });
  },

  me: (signal?: AbortSignal): Promise<UserInfo> => apiRequest<UserInfo>('auth/me', { signal }),
};
