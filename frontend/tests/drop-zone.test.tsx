/**
 * DropZone render + validation.
 * Focused: the "Analyze" button must be disabled with no file, and rejected
 * files must surface the reason. (The full upload→navigate interaction is
 * covered by tests/upload-flow.test.tsx with a mocked API.)
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen } from '@testing-library/react';
import { DropZone } from '@/components/contracts/drop-zone';
import { getRouterPushSpy, renderWithProviders } from '@/test/render';

// Self-contained factory: must not reference any imported bindings (vi.mock
// hoists the call above imports). The push spy lives on globalThis.
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

describe('DropZone', () => {
  beforeEach(() => getRouterPushSpy().mockReset());

  it('renders the upload card with the file picker labelled', () => {
    renderWithProviders(<DropZone />);
    expect(screen.getByText('Upload a contract')).toBeInTheDocument();
    // The drop area is a keyboard-accessible role="button" labelled for a11y.
    expect(screen.getByRole('button', { name: 'Choose a contract file' })).toBeInTheDocument();
  });

  it('has the Analyze button disabled when no file is selected', () => {
    renderWithProviders(<DropZone />);
    expect(screen.getByRole('button', { name: 'Analyze' })).toBeDisabled();
  });

  it('rejects unsupported file types and says why', async () => {
    renderWithProviders(<DropZone />);
    await pickFile(new File(['x'], 'photo.png'));
    expect(await screen.findByText(/Unsupported file type.*\.png/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Analyze' })).toBeDisabled();
  });

  it('accepts an allowed file and enables Analyze', async () => {
    renderWithProviders(<DropZone />);
    await pickFile(new File(['data'], 'msa.pdf'));
    expect(await screen.findByText('msa.pdf')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Analyze' })).toBeEnabled();
  });

  it('rejects empty files', async () => {
    renderWithProviders(<DropZone />);
    await pickFile(new File([], 'empty.txt'));
    expect(await screen.findByText('The file is empty.')).toBeInTheDocument();
  });

  it('associates the contract-type and side selects with their labels', () => {
    renderWithProviders(<DropZone />);
    expect(screen.getByLabelText('Contract type')).toBeInTheDocument();
    expect(screen.getByLabelText('Your side')).toBeInTheDocument();
  });
});

/**
 * Set a file on DropZone's hidden <input type="file">. The labelled element
 * is the drop-area div (a11y role=button); the input is aria-hidden from the
 * a11y tree, so we address it by its selector.
 */
function pickFile(file: File) {
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  if (!input) throw new Error('file input not found');
  fireEvent.change(input, { target: { files: [file] } });
}
