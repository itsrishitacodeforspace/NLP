# BharatContract Frontend — Testing & Accessibility Notes

Companion to [`README.md`](./README.md) §Testing / §Accessibility.

## Test suite map

| Path | Kind | Backend needed |
|---|---|---|
| `src/lib/__tests__/severity.test.ts` | unit | no |
| `src/lib/__tests__/format.test.ts` | unit | no |
| `src/lib/__tests__/utils.test.ts` | unit (`cn`) | no |
| `src/lib/__tests__/constants.test.ts` | unit | no |
| `src/lib/api/__tests__/errors.test.ts` | unit (`ApiError`) | no |
| `src/lib/api/__tests__/token-store.test.ts` | unit (mocked localStorage) | no |
| `src/lib/api/__tests__/client.test.ts` | unit (mocked `fetch`) | no |
| `src/lib/validation/__tests__/jobs.test.ts` | unit (zod `JobInfoSchema`) | no |
| `src/features/risks/__tests__/rule-category.test.ts` | unit (`ruleIdToCategory`) | no |
| `src/features/obligations/__tests__/ics.test.ts` | unit (ICS export) | no |
| `tests/severity-badge.test.tsx` | component | no |
| `tests/states.test.tsx` | component (Empty/Error/Loading) | no |
| `tests/drop-zone.test.tsx` | component (file validation) | no |
| `tests/upload-flow.test.tsx` | integration (MOCKED api + router) | no |
| `tests/auth-status.test.tsx` | component (AuthProvider, mocked `/me`) | no |
| `tests/real-backend.test.ts` | live (opt-in `RUN_REAL_BACKEND=1`; jobs need `RUN_REAL_BACKEND_JOBS=1`) | **yes** |
| `e2e/smoke.spec.ts` | Playwright (landing page only) | no |
| `e2e/backend.spec.ts` | Playwright (opt-in `RUN_E2E_BACKEND=1`) | **yes** |

Conventions:

- `src/test/render.tsx` — `renderWithProviders()` wraps components in
  QueryClient + Theme + Toast + Auth providers. `next/navigation` must be
  `vi.mock`'d per test file (self-contained factory; the push spy lives on
  `globalThis.__BC_TEST_ROUTER_PUSH`, accessible via `getRouterPushSpy()`).
- Every mocked test says so in its header comment.
- Component tests are intentionally NOT brittle: they assert roles/labels,
  not class strings.

### Tests skipped / not created because targets were in-flight

- **Obligations table / filtering component** — `src/components/obligations/*`
  did not exist at QA time; the obligations table test was skipped. The pure
  `src/features/obligations/ics.ts` ICS helper WAS created and is covered by
  `src/features/obligations/__tests__/ics.test.ts`.
- **`src/components/review/*`, `risks/*` (detail panels), `graph/*`,
  `comparison/*`** — in-flight; no component tests written for them yet.
  The badges in `src/components/risks/badges.tsx` were already stable and ARE
  tested (`tests/severity-badge.test.tsx`).
- **Login page component test** — `src/app/login*` was in-flight; the auth
  behavior it depends on (provider + token store) is tested instead.

## Pinned findings (behavior asserted as-is, NOT fixed — see report)

1. **AuthProvider `backendAuthEnabled` inversion**
   (`src/features/auth/auth-provider.tsx`):
   `backendAuthEnabled = me.data ? !me.data.authenticated : false`.
   Empirically, AuthStatus renders the "Auth off" span for ALL input
   combinations (auth off, auth on + logged in, 401 no token, stored user +
   401). Consequences: the signed-in branch (username · role + Sign out) is
   unreachable in practice, the "Sign in" link is dead UI, and the
   stored-user fallback is dead. Pinned in `tests/auth-status.test.tsx`.
   Likely intended: `me.data ? me.data.authenticated : false` with the
   "Auth off" branch gated on `!me.data || !me.data.authenticated`.
2. **`ruleIdToCategory('RISK_S124_001')` → "Other"**
   (`src/features/risks/index.ts`): the prefix table has `'S124'` but the
   backend emits `RISK_S124_001` (see `nlp/risk_scoring/rules.py` line ~993).
   The s.124 indemnity rule therefore lands in the "Other" bucket. Pinned in
   `src/features/risks/__tests__/rule-category.test.ts` with a comment.
3. **`ruleIdToCategory('RISK_DATA_MISSING')` → "Data protection"** — prefix
   matching is loose by design; pinned, not changed.
4. **Real-backend job pipeline hangs under vitest load** in this environment
   (uploads complete <5s via curl, but the worker appears starved under the
   jsdom+vitest process). The upload→poll tests are therefore guarded by an
   extra flag `RUN_REAL_BACKEND_JOBS=1`; the cheap read-only live checks
   (healthz/me/jobs) still run under `RUN_REAL_BACKEND=1` alone.

## Accessibility pass

Reviewed: `src/components/ui/*` (button, input, label, progress, alert,
state, card, badge, skeleton, separator), `src/components/layout/*`
(app-header, theme-toggle, auth-status, logout-button, toast, disclaimer,
theme-provider), `src/components/contracts/drop-zone.tsx`,
`src/components/risks/badges.tsx`.

### Confirmed good (no change needed)

- **focus-visible**: `Button`, `Input` and the dropzone's selects all use
  `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring`
  (button additionally `ring-offset-2`).
- **Icon-only buttons**: `ThemeToggle` → `aria-label="Switch to
  light/dark mode"`; dropzone remove-file button → `aria-label="Remove
  file"`. LogoutButton has visible "Sign out" text (not icon-only).
- **Roles**: `Alert` → `role="alert"`; `Spinner` → `role="status"`;
  `Progress` → `role="progressbar"` + `aria-valuenow/min/max` +
  `aria-label`; toasts live in an `aria-live="polite"` region with each
  toast `role="status"`.
- **Gauge svg**: `RiskGauge` → `role="img"` +
  `aria-label="Risk score N of 100, <level>"`.
- **Label associations**: dropzone uses `<Label htmlFor="contract-type">` +
  `<select id="contract-type">` (same for `user-role`). The file input is
  hidden but the drop area is a keyboard-accessible `role="button"`
  `tabIndex=0` with `aria-label="Choose a contract file"` and Enter/Space
  handling.
- **Landmarks**: `<header>`, `<main>`, `<footer>`, `nav aria-label="Primary"`.
- **Decorative icons** are `aria-hidden`.

### Fixes made (small, unambiguous)

1. `src/components/ui/state.tsx` — `ErrorState` now renders
   `role="alert"` so error announcements are conveyed to assistive
   technology. (Only change to a product file in this pass.)

### Findings left to the owning agents (not fixed — out of my file scope)

- `AuthStatus` "Auth off" span uses `hidden ... md:inline` (CSS-only
  responsive hiding); at narrow viewports screen readers also can't see the
  auth state. Consider `aria-hidden` toggling or a `title` fallback for
  mobile.
- `AppHeader` nav links have no `aria-current="page"` on the active route
  (Next.js `usePathname` available in a client component).
- Dropzone reject-reason paragraph uses a `p` with `text-destructive`;
  giving it `role="alert"` (or `aria-live="assertive"`) would announce
  validation failures. The dropzone is owned by the contracts agent.
- The login form (in-flight) should use `aria-invalid` + described-by
  associations on failure — noted for the auth agent.
