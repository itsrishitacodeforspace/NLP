/**
 * Upload flow — DropZone → contractsApi.upload → navigate to /jobs/{id}.
 *
 * MOCKED — does not hit the real backend. `contractsApi.upload` is vi.mocked
 * to return a JobInfo; we assert the mutation calls it and would navigate.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen } from '@testing-library/react';
import { DropZone } from '@/components/contracts/drop-zone';
import { getRouterPushSpy, renderWithProviders } from '@/test/render';
import type { JobInfo } from '@/types';

// Self-contained factory (vi.mock hoists above imports — no imported bindings).
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: (p: string) => {
      const spy = globalThis.__BC_TEST_ROUTER_PUSH as ((path: string) => void) | undefined;
      if (spy) spy(p);
    },
    replace: () => {},
    back: () => {},
    forward: () => {},
    refresh: () => {},
    prefetch: () => {},
  }),
  usePathname: () => '/',
  useSearchParams: () => new URLSearchParams(),
  useRouterState: () => ({ asPath: '/', pathname: '/' }),
}));

const pushSpy = getRouterPushSpy();

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    contractsApi: {
      ...actual.contractsApi,
      upload: vi.fn(),
    },
  };
});

import { contractsApi } from '@/lib/api';

const uploadMock = contractsApi.upload as unknown as ReturnType<typeof vi.fn>;

const JOB: JobInfo = {
  job_id: 'job-9001',
  contract_id: 'c-77',
  owner: 'anonymous',
  status: 'queued',
  progress: 0,
  message: 'Queued',
  created_at: '2026-11-03T12:00:00',
  finished_at: null,
  result: null,
  error: null,
  result_error: null,
};

describe('upload flow (MOCKED)', () => {
  beforeEach(() => {
    pushSpy.mockReset();
    uploadMock.mockReset();
  });

  it('calls contractsApi.upload with the chosen file and navigates to the job', async () => {
    uploadMock.mockResolvedValueOnce(JOB);
    renderWithProviders(<DropZone />);

    await pickFile(new File(['contract bytes'], 'msa.txt'));
    expect(screen.getByText('msa.txt')).toBeInTheDocument();
    expect(uploadMock).not.toHaveBeenCalled();

    const analyze = screen.getByRole('button', { name: 'Analyze' });
    expect(analyze).toBeEnabled();
    fireEvent.click(analyze);

    // The mutation invoked the mocked API exactly once, with our file.
    await vi.waitFor(() => expect(uploadMock).toHaveBeenCalledTimes(1));
    const arg = uploadMock.mock.calls[0][0];
    expect(arg.file).toBeInstanceOf(File);
    expect(arg.file.name).toBe('msa.txt');
    expect(arg.contractType).toBe('Other');
    expect(arg.userRole).toBe('Customer');

    // On success it navigates to the job page.
    await vi.waitFor(() => expect(pushSpy).toHaveBeenCalledWith('/jobs/job-9001'));
  });

  it('does not navigate when the upload is rejected', async () => {
    renderWithProviders(<DropZone />);
    await pickFile(new File(['x'], 'photo.png'));
    await screen.findByText(/Unsupported file type/);
    expect(screen.getByRole('button', { name: 'Analyze' })).toBeDisabled();
    expect(uploadMock).not.toHaveBeenCalled();
    expect(pushSpy).not.toHaveBeenCalled();
  });
});

function pickFile(file: File) {
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  if (!input) throw new Error('file input not found');
  fireEvent.change(input, { target: { files: [file] } });
}
