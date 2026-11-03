/**
 * Central API error type. All client methods throw ApiError on non-2xx
 * responses; callers (TanStack Query / react-query) surface it uniformly.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }

  /** 401 — token missing/invalid/expired. Triggers re-auth. */
  get isAuth(): boolean {
    return this.status === 401;
  }
  get isForbidden(): boolean {
    return this.status === 403;
  }
  /** 404 — not found OR row-level-security scoped-out (backend returns 404 for both). */
  get isNotFound(): boolean {
    return this.status === 404;
  }
  /** 409 — contract still processing, or analysis failed. */
  get isConflict(): boolean {
    return this.status === 409;
  }
  get isTooLarge(): boolean {
    return this.status === 413;
  }
  get isThrottled(): boolean {
    return this.status === 429;
  }
}

export function isApiError(e: unknown): e is ApiError {
  return e instanceof ApiError;
}

/** Human-readable message for an unknown error. */
export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) return e.detail;
  if (e instanceof Error) return e.message;
  return String(e);
}
