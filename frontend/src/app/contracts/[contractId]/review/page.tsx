import type { ReviewData } from '@/features/review/review-workspace';
import { ReviewWorkspace } from '@/features/review/review-workspace';

/**
 * Contract Review page.
 *
 * Data loading is client-side (react-query hooks in `ReviewWorkspace`), which
 * is the path that works in this environment: the backend serves `/api/v1/*`
 * and the Next.js dev proxy rewrites same-origin `/api/...` ->
 * `${BACKEND_URL}/api/...`.
 *
 * NOTE (shared-file issue, reported not fixed): `src/lib/server-fetch.ts`
 * builds URLs as `${BASE}/api/contracts/...` — missing the `/v1` segment that
 * this backend serves — so server-side fetch cannot be used here. The page
 * renders a loading skeleton on the server and hydrates from the API on the
 * client.
 */
export default function ContractReviewPage({ params }: { params: { contractId: string } }) {
  const contractId = params.contractId;
  // `data` is null: see the note above. Kept on the prop so a future fix to
  // server-fetch.ts can seed the workspace without changing its API.
  const data: ReviewData | null = null;
  return <ReviewWorkspace contractId={contractId} data={data} />;
}
