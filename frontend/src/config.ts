const trimTrailingSlash = (value: string) => value.replace(/\/+$/, '');

/** Same-origin by default: the SPA and the API share a Static Web App. */
export const API_BASE_URL = trimTrailingSlash(import.meta.env.VITE_API_BASE_URL ?? '');

/**
 * Entra ID (Azure AD) app registration used for MSAL.js sign-in (public client,
 * PKCE, no secret). One App Registration serves both roles: SPA client and the
 * API resource whose scope is requested — see `infrastructure/scripts/register-entra-app.sh`.
 */
export const MSAL_CLIENT_ID = import.meta.env.VITE_MSAL_CLIENT_ID ?? '';
export const MSAL_TENANT_ID = import.meta.env.VITE_MSAL_TENANT_ID ?? '';
/** Requested on login and attached as the Bearer token's audience for `/api` calls. */
export const MSAL_API_SCOPE = import.meta.env.VITE_MSAL_API_SCOPE ?? '';

/*
 * Local-development escape hatch for machines with no Easy Auth host.
 *
 * Both are gated on `import.meta.env.DEV`, which Vite replaces with the literal
 * `false` in a production build — so the branch is dead code that Rollup drops,
 * and `VITE_AUTH_DEV_TOKEN` is never inlined into the bundle even if it is set
 * in the build environment. Without the gate, a production build with the flag
 * on would ship with the sign-in gate removed and a token embedded in the JS.
 */
export const AUTH_DEV_BYPASS =
  import.meta.env.DEV && import.meta.env.VITE_AUTH_DEV_BYPASS === 'true';
export const AUTH_DEV_TOKEN = import.meta.env.DEV
  ? (import.meta.env.VITE_AUTH_DEV_TOKEN ?? '')
  : '';

/**
 * Azure Blob Storage accepts a single PUT up to 256 MiB, but a failed 50 MB+
 * upload means starting over. Above the threshold we stage blocks instead.
 */
export const UPLOAD_BLOCK_SIZE = Number(import.meta.env.VITE_UPLOAD_BLOCK_SIZE ?? 8 * 1024 * 1024);
export const UPLOAD_SINGLE_SHOT_LIMIT = 32 * 1024 * 1024;
export const UPLOAD_BLOCK_CONCURRENCY = 3;

export const JOBS_STORAGE_KEY = 'ai-agent-chat.jobs.v1';
/** `ThreadStore` — the conversation list. See the identity note in lib/threads. */
export const THREAD_STORAGE_KEY = 'ai-agent-chat.threads.v3';
/** Previous single-conversation key, read once so an in-flight chat is not lost. */
export const THREAD_STORAGE_KEY_V2 = 'ai-agent-chat.thread.v2';
/** Conversations kept in the switcher before the oldest are dropped. */
export const MAX_TRACKED_THREADS = 20;

/** Confirmations the user has already answered, so a refresh cannot re-offer them. */
export const CONFIRMATION_RESOLUTIONS_KEY = 'ai-agent-chat.confirmations.v1';
export const CONFIRMATION_RESOLUTION_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000;
/** Partial assistant reply, kept so a refresh mid-stream does not lose it. */
export const STREAM_DRAFT_STORAGE_KEY = 'ai-agent-chat.stream-draft.v1';

/**
 * How often the in-flight reply is written to localStorage. Deltas flush once
 * per frame; persisting at that rate would mean ~60 synchronous writes a second
 * for no benefit, so the draft lags by at most this much.
 */
export const STREAM_DRAFT_PERSIST_MS = 1_000;

/** Older drafts are ignored: a week-old fragment is noise, not a recovery. */
export const STREAM_DRAFT_MAX_AGE_MS = 24 * 60 * 60 * 1000;

/** Poll fast at first, then back off so long-running indexing jobs stay cheap. */
export const JOB_POLL_INTERVAL_MS = 2_000;
export const JOB_POLL_MAX_INTERVAL_MS = 15_000;
/** Terminal jobs older than this are pruned from localStorage on boot. */
export const JOB_RETENTION_MS = 24 * 60 * 60 * 1000;
