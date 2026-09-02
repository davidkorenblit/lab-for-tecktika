import { API_BASE_URL } from '@/config';
import { clearCachedSession, getAccessToken, refreshSession } from './auth';

export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }

  get isUnauthorized(): boolean {
    return this.status === 401 || this.status === 403;
  }
}

export interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown;
  /** Set for endpoints that must not retry after a token refresh. */
  noRetry?: boolean;
}

function resolveUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  return `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`;
}

/**
 * The single choke point every API call goes through — this is the
 * "interceptor". It attaches the Easy Auth bearer token, sends the auth cookie,
 * and on a 401 refreshes the session once and replays the request.
 */
export async function authorizedFetch(path: string, options: RequestOptions = {}): Promise<Response> {
  const { body, noRetry, headers, ...rest } = options;

  const send = async (token: string | null): Promise<Response> => {
    const merged = new Headers(headers);
    if (!merged.has('Accept')) merged.set('Accept', 'application/json');
    if (token) merged.set('Authorization', `Bearer ${token}`);

    let payload: BodyInit | undefined;
    if (body instanceof FormData || body instanceof Blob || typeof body === 'string') {
      payload = body;
    } else if (body !== undefined) {
      payload = JSON.stringify(body);
      if (!merged.has('Content-Type')) merged.set('Content-Type', 'application/json');
    }

    return fetch(resolveUrl(path), {
      ...rest,
      headers: merged,
      body: payload,
      // Easy Auth's session cookie rides along for hosts that use it instead of
      // (or in addition to) the bearer token.
      credentials: 'include',
    });
  };

  let response = await send(await getAccessToken());

  if (response.status === 401 && !noRetry) {
    clearCachedSession();
    const refreshed = await refreshSession();
    response = await send(refreshed.token);
  }

  return response;
}

async function parseBody(response: Response): Promise<unknown> {
  const contentType = response.headers.get('content-type') ?? '';
  if (response.status === 204) return null;
  if (contentType.includes('application/json')) return response.json().catch(() => null);
  return response.text().catch(() => null);
}

function errorMessage(status: number, body: unknown): string {
  if (body && typeof body === 'object') {
    const record = body as Record<string, unknown>;
    const message = record.message ?? record.error ?? record.detail;
    if (typeof message === 'string' && message.trim()) return message;
  }
  if (typeof body === 'string' && body.trim()) return body.slice(0, 300);
  return `Request failed with status ${status}`;
}

/** JSON request helper. Throws `ApiError` for any non-2xx response. */
export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await authorizedFetch(path, options);
  const body = await parseBody(response);

  if (!response.ok) {
    throw new ApiError(errorMessage(response.status, body), response.status, body);
  }

  return body as T;
}

export const api = {
  get: <T>(path: string, options?: RequestOptions) => apiRequest<T>(path, { ...options, method: 'GET' }),
  post: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    apiRequest<T>(path, { ...options, method: 'POST', body }),
  put: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    apiRequest<T>(path, { ...options, method: 'PUT', body }),
  del: <T>(path: string, options?: RequestOptions) =>
    apiRequest<T>(path, { ...options, method: 'DELETE' }),
  /** Raw response — used by the SSE stream, which needs `response.body`. */
  raw: authorizedFetch,
};
