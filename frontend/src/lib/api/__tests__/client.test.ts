import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { apiRequest } from '@/lib/api/client';

type FetchMock = ReturnType<typeof vi.fn>;

function jsonResponse(status: number, body: unknown, init?: ResponseInit): Response {
  return new Response(typeof body === 'string' ? body : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
}

describe('api/client.ts — apiRequest', () => {
  let fetchMock: FetchMock;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('returns parsed JSON on 200 and hits the versioned route', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, { ok: true }));
    await expect(apiRequest('x')).resolves.toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    // URL shape: `${BACKEND_URL}/api/v1/<path>` (versioned backend routes).
    expect(String(url)).toMatch(/\/api\/v1\/x$/);
    expect(init.headers['Content-Type']).toBe('application/json');
  });

  it('returns undefined on 204 No Content', async () => {
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));
    await expect(apiRequest('x')).resolves.toBeUndefined();
  });

  it.each([
    [400, 'bad request'],
    [401, 'unauthorized'],
    [403, 'forbidden'],
    [404, 'not found'],
    [409, 'still processing'],
    [413, 'oversize'],
    [429, 'slow down'],
  ] as const)('throws ApiError with status+detail on %i', async (status, detail) => {
    fetchMock.mockResolvedValueOnce(jsonResponse(status, { detail }));
    await expect(apiRequest('x')).rejects.toMatchObject({ name: 'ApiError', status, detail });
  });

  it('extracts a non-string detail object via JSON.stringify', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(422, { detail: ['field', 'is', 'bad'] }));
    await expect(apiRequest('x')).rejects.toMatchObject({
      status: 422,
      detail: JSON.stringify(['field', 'is', 'bad']),
    });
  });

  it('falls back to "Request failed (status)" when the body has no detail', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(500, {}));
    await expect(apiRequest('x')).rejects.toMatchObject({
      status: 500,
      detail: 'Request failed (500)',
    });
  });

  it('throws ApiError(0) when the network itself fails', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'));
    const err: any = await apiRequest('x').catch((e) => e);
    expect(err).toBeInstanceOf(Error);
    expect(err.name).toBe('ApiError');
    expect(err.status).toBe(0);
    expect(err.message).toContain('Cannot reach the backend');
  });

  it('re-throws AbortError untouched (no ApiError wrapping)', async () => {
    const abort = new DOMException('Aborted', 'AbortError');
    fetchMock.mockRejectedValueOnce(abort);
    await expect(apiRequest('x', { signal: new AbortController().signal })).rejects.toBe(abort);
  });

  it('sends JSON body for POST', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, { ok: 1 }));
    await apiRequest('things', { method: 'POST', body: { a: 1 } });
    const [, init] = fetchMock.mock.calls[0];
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body)).toEqual({ a: 1 });
  });

  it('does NOT attach a Content-Type header for FormData', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, { ok: 1 }));
    const fd = new FormData();
    fd.append('file', new Blob(['x']), 'a.txt');
    await apiRequest('contracts/upload', { method: 'POST', formData: fd });
    const [, init] = fetchMock.mock.calls[0];
    expect(init.body).toBe(fd);
    expect(init.headers['Content-Type']).toBeUndefined();
  });

  describe('401 handling', () => {
    it('dispatches bharatcontract:unauthorized on 401', async () => {
      const listener = vi.fn();
      window.addEventListener('bharatcontract:unauthorized', listener);
      fetchMock.mockResolvedValueOnce(jsonResponse(401, { detail: 'expired' }));
      await apiRequest('jobs').catch(() => undefined);
      expect(listener).toHaveBeenCalledTimes(1);
      window.removeEventListener('bharatcontract:unauthorized', listener);
    });

    it('does NOT dispatch the event when noAuth is set (login call)', async () => {
      const listener = vi.fn();
      window.addEventListener('bharatcontract:unauthorized', listener);
      fetchMock.mockResolvedValueOnce(jsonResponse(401, { detail: 'expired' }));
      await apiRequest('auth/me', { noAuth: true }).catch(() => undefined);
      expect(listener).not.toHaveBeenCalled();
      window.removeEventListener('bharatcontract:unauthorized', listener);
    });

    it('does NOT dispatch the event on other non-2xx statuses', async () => {
      const listener = vi.fn();
      window.addEventListener('bharatcontract:unauthorized', listener);
      fetchMock.mockResolvedValueOnce(jsonResponse(403, { detail: 'forbidden' }));
      await apiRequest('jobs').catch(() => undefined);
      expect(listener).not.toHaveBeenCalled();
      window.removeEventListener('bharatcontract:unauthorized', listener);
    });
  });

  describe('bearer token attachment', () => {
    it('attaches Authorization when a token is stored', async () => {
      vi.spyOn(await import('@/lib/api/token-store'), 'getToken').mockReturnValue('tok-1');
      fetchMock.mockResolvedValueOnce(jsonResponse(200, { ok: 1 }));
      await apiRequest('jobs');
      const [, init] = fetchMock.mock.calls[0];
      expect(init.headers['Authorization']).toBe('Bearer tok-1');
    });

    it('omits Authorization when noAuth is set even with a stored token', async () => {
      vi.spyOn(await import('@/lib/api/token-store'), 'getToken').mockReturnValue('tok-1');
      fetchMock.mockResolvedValueOnce(jsonResponse(200, { ok: 1 }));
      await apiRequest('auth/token', { noAuth: true });
      const [, init] = fetchMock.mock.calls[0];
      expect(init.headers['Authorization']).toBeUndefined();
    });

    it('omits Authorization when no token is stored', async () => {
      vi.spyOn(await import('@/lib/api/token-store'), 'getToken').mockReturnValue(null);
      fetchMock.mockResolvedValueOnce(jsonResponse(200, { ok: 1 }));
      await apiRequest('jobs');
      const [, init] = fetchMock.mock.calls[0];
      expect(init.headers['Authorization']).toBeUndefined();
    });
  });
});
