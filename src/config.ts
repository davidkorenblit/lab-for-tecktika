const trimTrailingSlash = (value: string) => value.replace(/\/+$/, '');

/** Same-origin by default: the SPA and the API share a Static Web App. */
export const API_BASE_URL = trimTrailingSlash(import.meta.env.VITE_API_BASE_URL ?? '');

/** Easy Auth endpoints (`/.auth/me`, `/.auth/refresh`, `/.auth/login/aad`). */
export const AUTH_BASE_URL = trimTrailingSlash(import.meta.env.VITE_AUTH_BASE_URL ?? '');

export const AUTH_DEV_BYPASS = import.meta.env.VITE_AUTH_DEV_BYPASS === 'true';
export const AUTH_DEV_TOKEN = import.meta.env.VITE_AUTH_DEV_TOKEN ?? '';

/**
 * Azure Blob Storage accepts a single PUT up to 256 MiB, but a failed 50 MB+
 * upload means starting over. Above the threshold we stage blocks instead.
 */
export const UPLOAD_BLOCK_SIZE = Number(import.meta.env.VITE_UPLOAD_BLOCK_SIZE ?? 8 * 1024 * 1024);
export const UPLOAD_SINGLE_SHOT_LIMIT = 32 * 1024 * 1024;
export const UPLOAD_BLOCK_CONCURRENCY = 3;

export const JOBS_STORAGE_KEY = 'ai-agent-chat.jobs.v1';
export const CONVERSATION_STORAGE_KEY = 'ai-agent-chat.conversation.v1';

/** Poll fast at first, then back off so long-running indexing jobs stay cheap. */
export const JOB_POLL_INTERVAL_MS = 2_000;
export const JOB_POLL_MAX_INTERVAL_MS = 15_000;
/** Terminal jobs older than this are pruned from localStorage on boot. */
export const JOB_RETENTION_MS = 24 * 60 * 60 * 1000;
