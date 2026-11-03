import { expect, test } from '@playwright/test';

/**
 * OPT-IN e2e against the real FastAPI backend.
 *
 * Run with:  RUN_E2E_BACKEND=1 npm run e2e
 * (and the backend reachable at BACKEND_URL, default http://127.0.0.1:8010).
 *
 * Skipped entirely when the flag is unset or the backend is unreachable, so
 * it never fails in an environment without the API. The probe is a real
 * `test` (so it shows up as skipped, not as a broken suite) and the live
 * test depends on it.
 */
const BACKEND = process.env.BACKEND_URL || 'http://127.0.0.1:8010';
const OPT_IN = process.env.RUN_E2E_BACKEND === '1' || process.env.RUN_E2E_BACKEND === 'true';

test.describe('real backend (live)', () => {
  test('backend is reachable (probe)', async () => {
    if (!OPT_IN) {
      test.skip(true, 'RUN_E2E_BACKEND not set — opt-in suite');
    }
    let ok = false;
    try {
      ok = (await fetch(`${BACKEND.replace(/\/$/, '')}/healthz`)).ok;
    } catch {
      ok = false;
    }
    if (!ok) {
      test.skip(true, `backend at ${BACKEND} unreachable — opt-in suite`);
    }
  });

  test('upload a contract end-to-end and land on the job page', async ({ page }) => {
    // Self-contained skip logic (mirrors the probe) so the suite never fails
    // when the backend is absent.
    test.skip(!OPT_IN, 'RUN_E2E_BACKEND not set');
    let reachable = false;
    try {
      reachable = (await fetch(`${BACKEND.replace(/\/$/, '')}/healthz`)).ok;
    } catch {
      reachable = false;
    }
    test.skip(!reachable, `backend at ${BACKEND} unreachable`);

    await page.goto('/');
    const input = page.locator('input[type="file"]');
    await input.setInputFiles({
      name: 'msa.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from(
        [
          'MASTER SERVICES AGREEMENT',
          'Provider aggregate liability shall be unlimited; Provider shall not be liable for any indirect damages.',
          'This Agreement is governed by the laws of England and Wales.',
          'This Agreement shall automatically renew unless either party gives written notice of non-renewal at least sixty days prior to the end of the term.',
        ].join('\n')
      ),
    });
    await expect(page.getByRole('button', { name: 'Analyze' })).toBeEnabled();
    await page.getByRole('button', { name: 'Analyze' }).click();

    await expect(page).toHaveURL(/\/jobs\/.+/, { timeout: 30_000 });
    // The job page polls until terminal; wait for a stage label to appear.
    await expect(page.getByText(/Waiting to start|Analyzing|Analysis complete|Analysis failed/).first()).toBeVisible({
      timeout: 120_000,
    });
  });
});
