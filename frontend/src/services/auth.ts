import { AUTH_BASE_URL, AUTH_DEV_BYPASS, AUTH_DEV_TOKEN } from '@/config';
import type { AuthSession, ClientPrincipal } from '@/types';

/**
 * Easy Auth session handling.
 *
 * `/.auth/me` answers in one of two shapes depending on the host:
 *   - Static Web Apps: `{ clientPrincipal: {...} }`
 *   - App Service / Functions Easy Auth: `[{ access_token, id_token, ... }]`
 * Both are accepted here, and the token is looked for in the token-store
 * payload first, then in the principal's claims.
 */

const EMPTY_SESSION: AuthSession = { principal: null, token: null, expiresAt: null };

/** Refresh this long before the token actually expires. */
const EXPIRY_SKEW_MS = 60_000;

let cachedSession: AuthSession | null = null;
let inflight: Promise<AuthSession> | null = null;

export function clearCachedSession(): void {
  cachedSession = null;
  inflight = null;
}

/**
 * Loads the session, de-duplicating concurrent callers so a burst of API calls
 * on first paint results in a single `/.auth/me` request.
 */
export async function loadSession(force = false): Promise<AuthSession> {
  if (AUTH_DEV_BYPASS) {
    cachedSession = {
      principal: {
        identityProvider: 'dev',
        userId: 'local-dev',
        userDetails: 'dev@localhost',
        userRoles: ['authenticated'],
      },
      token: AUTH_DEV_TOKEN || null,
      expiresAt: null,
    };
    return cachedSession;
  }

  if (!force && cachedSession && !isExpired(cachedSession)) return cachedSession;
  if (!force && inflight) return inflight;

  inflight = fetchSession()
    .then((session) => {
      cachedSession = session;
      return session;
    })
    .finally(() => {
      inflight = null;
    });

  return inflight;
}

async function fetchSession(): Promise<AuthSession> {
  const response = await fetch(`${AUTH_BASE_URL}/.auth/me`, {
    headers: { Accept: 'application/json' },
    credentials: 'include',
    cache: 'no-store',
  });

  // Anonymous users get 401/403 from some hosts and an empty body from others.
  if (response.status === 401 || response.status === 403) return EMPTY_SESSION;
  if (!response.ok) {
    throw new Error(`Failed to load auth session (${response.status})`);
  }

  const payload = (await response.json().catch(() => null)) as unknown;
  return normaliseSession(payload);
}

/**
 * Asks Easy Auth to refresh the token store, then re-reads the session. Called
 * once on a 401 before surfacing the failure to the caller.
 */
export async function refreshSession(): Promise<AuthSession> {
  if (AUTH_DEV_BYPASS) return loadSession(true);
  try {
    await fetch(`${AUTH_BASE_URL}/.auth/refresh`, {
      credentials: 'include',
      cache: 'no-store',
    });
  } catch {
    /* refresh is best effort; loadSession below decides the outcome */
  }
  return loadSession(true);
}

/** The value the API client puts behind `Bearer `. */
export async function getAccessToken(): Promise<string | null> {
  const session = await loadSession();
  return session.token;
}

export function loginUrl(provider = 'aad', redirect = window.location.pathname): string {
  return `${AUTH_BASE_URL}/.auth/login/${provider}?post_login_redirect_uri=${encodeURIComponent(redirect)}`;
}

export function logoutUrl(redirect = '/'): string {
  return `${AUTH_BASE_URL}/.auth/logout?post_logout_redirect_uri=${encodeURIComponent(redirect)}`;
}

export function isAuthenticated(session: AuthSession | null | undefined): boolean {
  return Boolean(session?.principal);
}

function isExpired(session: AuthSession): boolean {
  if (session.expiresAt === null) return false;
  return Date.now() >= session.expiresAt - EXPIRY_SKEW_MS;
}

/* ------------------------------- normalising ------------------------------ */

interface TokenStoreEntry {
  access_token?: string;
  id_token?: string;
  expires_on?: string | number;
  provider_name?: string;
  user_id?: string;
  user_claims?: Array<{ typ: string; val: string }>;
}

function normaliseSession(payload: unknown): AuthSession {
  if (!payload) return EMPTY_SESSION;

  // App Service / Functions Easy Auth token store.
  if (Array.isArray(payload)) {
    const entry = payload[0] as TokenStoreEntry | undefined;
    if (!entry) return EMPTY_SESSION;
    const claims = entry.user_claims ?? [];
    return {
      principal: {
        identityProvider: entry.provider_name ?? 'aad',
        userId: entry.user_id ?? claimValue(claims, 'oid') ?? '',
        userDetails:
          entry.user_id ?? claimValue(claims, 'preferred_username') ?? claimValue(claims, 'name') ?? '',
        userRoles: claims.filter((c) => c.typ === 'roles').map((c) => c.val),
        claims,
      },
      token: entry.access_token ?? entry.id_token ?? null,
      expiresAt: parseExpiry(entry.expires_on),
    };
  }

  const record = payload as { clientPrincipal?: ClientPrincipal | null };
  const principal = record.clientPrincipal ?? null;
  if (!principal) return EMPTY_SESSION;

  const claims = principal.claims ?? [];
  // SWA does not return the raw token by default; it shows up as a claim when
  // the app requests it. Falling through to null is fine — the client then
  // relies on the auth cookie plus the principal header SWA injects server-side.
  const token =
    claimValue(claims, 'id_token') ??
    claimValue(claims, 'access_token') ??
    claimValue(claims, 'idp_access_token') ??
    null;

  if (!token && import.meta.env.DEV) {
    console.warn(
      '[auth] /.auth/me returned no bearer token; API calls will rely on the Easy Auth cookie.',
    );
  }

  return {
    principal,
    token,
    expiresAt: parseExpiry(claimValue(claims, 'exp')),
  };
}

function claimValue(claims: Array<{ typ: string; val: string }>, type: string): string | undefined {
  return claims.find((claim) => claim.typ === type || claim.typ.endsWith(`/${type}`))?.val;
}

function parseExpiry(value: string | number | undefined): number | null {
  if (value === undefined) return null;
  if (typeof value === 'number') return value > 1e12 ? value : value * 1000;
  const asNumber = Number(value);
  if (!Number.isNaN(asNumber) && asNumber > 0) return asNumber > 1e12 ? asNumber : asNumber * 1000;
  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? null : parsed;
}
