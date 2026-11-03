import { expect, test } from '@playwright/test';

/**
 * Smoke test — requires ONLY the Next.js dev server (no backend needed).
 * The landing page renders its chrome (title + disclaimer) without any
 * successful API call, so this passes with the backend down.
 */
test.describe('landing page', () => {
  test('renders the app title', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'BharatContract AI' })).toBeVisible();
    expect(page).toHaveTitle(/BharatContract AI/);
  });

  test('shows the mandatory disclaimer', async ({ page }) => {
    await page.goto('/');
    await expect(
      page.getByText(/does not constitute legal advice/i)
    ).toBeVisible();
  });

  test('renders the upload card with a disabled Analyze button', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByText('Upload a contract')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Analyze' })).toBeDisabled();
  });
});
