import {
  PublicClientApplication,
  InteractionRequiredAuthError,
  type AccountInfo,
} from '@azure/msal-browser';
import { AUTH_DEV_BYPASS, AUTH_DEV_TOKEN, MSAL_API_SCOPE, MSAL_CLIENT_ID, MSAL_TENANT_ID } from '@/config';
import type { AuthSession, ClientPrincipal } from '@/types';

/**
 * MSAL.js session handling (public client, PKCE, no secret).
 *
 * One Entra ID app registration serves both roles: the SPA client that signs
 * the user in, and the API resource whose scope (`MSAL_API_SCOPE`) is
 * requested on login and attached as the access token's audience. The backend
 * validates that token itself — there is no server-side auth host involved.
 */

const EMPTY_SESSION: AuthSession = { principal: null, token: null, expiresAt: null };

const loginRequest = { scopes: [MSAL_API_SCOPE] };

let cachedSession: AuthSession | null = null;
let inflight: Promise<AuthSession> | null = null;

/**
 * Built lazily, not at module scope: this file is imported by code (e.g.
 * `apiClient.ts`) that other modules pull in under Node-environment unit
 * tests with no `window`, and MSAL's config touches `window.location` at
 * construction time.
 */
let msal: PublicClientApplication | null = null;
function getMsalInstance(): PublicClientApplication {
  if (!msal) {
    msal = new PublicClientApplication({
      auth: {
        clientId: MSAL_CLIENT_ID,
        authority: `https://login.microsoftonline.com/${MSAL_TENANT_ID}`,
        redirectUri: window.location.origin,
        postLogoutRedirectUri: window.location.origin,
      },
      cache: {
        // Survives a full page redirect (required for the auth code flow)
        // without leaking the token to other tabs/sessions the way
        // localStorage would.
        cacheLocation: 'sessionStorage',
      },
    });
  }
  return msal;
}

/** Initializes MSAL and consumes the redirect response exactly once per page load. */
let initPromise: Promise<void> | null = null;
function ensureInitialized(): Promise<void> {
  if (!initPromise) {
    const instance = getMsalInstance();
    initPromise = instance
      .initialize()
      .then(() => instance.handleRedirectPromise())
      .then(() => undefined);
  }
  return initPromise;
}

export function clearCachedSession(): void {
  cachedSession = null;
  inflight = null;
}

/**
 * Loads the session, de-duplicating concurrent callers so a burst of API calls
 * on first paint results in a single silent-token acquisition.
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

  if (!force && cachedSession) return cachedSession;
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
  await ensureInitialized();
  const instance = getMsalInstance();

  const account = instance.getAllAccounts()[0];
  if (!account) return EMPTY_SESSION;

  try {
    const result = await instance.acquireTokenSilent({ ...loginRequest, account });
    return toSession(result.account, result.accessToken, result.expiresOn);
  } catch (error) {
    // A silent refresh can genuinely need interaction (e.g. revoked consent,
    // expired session on the identity provider's side). Surface as signed-out
    // rather than throwing — the sign-in screen's button starts a fresh redirect.
    if (error instanceof InteractionRequiredAuthError) return EMPTY_SESSION;
    throw error;
  }
}

/** Re-attempts a silent token acquisition. Called once on a 401 before giving up. */
export async function refreshSession(): Promise<AuthSession> {
  if (AUTH_DEV_BYPASS) return loadSession(true);
  return loadSession(true);
}

/** The value the API client puts behind `Bearer `. */
export async function getAccessToken(): Promise<string | null> {
  const session = await loadSession();
  return session.token;
}

/** Starts the MSAL redirect sign-in flow. Navigates away; does not return. */
export async function login(): Promise<void> {
  await ensureInitialized();
  await getMsalInstance().loginRedirect(loginRequest);
}

/** Starts the MSAL redirect sign-out flow. Navigates away; does not return. */
export async function logout(): Promise<void> {
  await ensureInitialized();
  const instance = getMsalInstance();
  const account = instance.getAllAccounts()[0];
  clearCachedSession();
  await instance.logoutRedirect({ account });
}

export function isAuthenticated(session: AuthSession | null | undefined): boolean {
  return Boolean(session?.principal);
}

function toSession(account: AccountInfo, token: string, expiresOn: Date | null): AuthSession {
  const claims = (account.idTokenClaims ?? {}) as Record<string, unknown>;
  const roles = Array.isArray(claims.roles) ? (claims.roles as string[]) : [];

  const principal: ClientPrincipal = {
    identityProvider: 'aad',
    userId: account.localAccountId,
    userDetails: account.username,
    userRoles: roles,
  };

  return {
    principal,
    token,
    expiresAt: expiresOn ? expiresOn.getTime() : null,
  };
}
