import { MAX_TRACKED_THREADS, THREAD_STORAGE_KEY } from '@/config';
import { uid } from '@/lib/format';
import { readSessionJson, writeSessionJson } from '@/lib/storage';

/**
 * The list of conversations this browser knows about.
 *
 * `threadId` is minted here and is stable for the life of a conversation — it is
 * what the React Query cache is keyed on. `conversationId` is the backend's name
 * for the same thing and is only ever sent in request bodies. Keeping them apart
 * is what stops a server id arriving mid-stream from moving the cache entry the
 * stream is writing into.
 *
 * Scoped to the browsing session, not the browser. A refresh keeps the
 * conversation - which 2.1 and 2.3 both require - while closing the tab ends
 * it, so signing in again starts on a clean conversation instead of resuming
 * one from days ago. There is deliberately no conversation list: the API has
 * no conversations endpoint, so a list could only ever live in this browser,
 * and a history that vanishes on another device is worse than no history.
 */
export interface ThreadRecord {
  threadId: string;
  conversationId?: string;
  /** First words of the opening message; falls back to a date in the UI. */
  title?: string;
  lastActiveAt: number;
  /**
   * Created by the user and not yet named by the backend. Asking
   * `/api/chat/history` without a conversationId returns the most recent
   * conversation — the one being left behind — so a fresh thread loads nothing
   * and lets the first message bring the server-side conversation into being.
   */
  fresh?: boolean;
}

export interface ThreadStore {
  activeThreadId: string;
  threads: ThreadRecord[];
}

export function newThread(fresh = false): ThreadRecord {
  return { threadId: uid('thread'), lastActiveAt: Date.now(), ...(fresh ? { fresh } : {}) };
}

function emptyStore(): ThreadStore {
  const thread = newThread();
  return { activeThreadId: thread.threadId, threads: [thread] };
}

export function loadThreadStore(): ThreadStore {
  const stored = readSessionJson<ThreadStore | null>(THREAD_STORAGE_KEY, null);
  if (stored && Array.isArray(stored.threads) && stored.threads.length > 0) {
    const threads = stored.threads.filter(
      (thread): thread is ThreadRecord => Boolean(thread) && typeof thread.threadId === 'string',
    );
    if (threads.length > 0) {
      const active = threads.some((thread) => thread.threadId === stored.activeThreadId)
        ? stored.activeThreadId
        : threads[0].threadId;
      return { activeThreadId: active, threads };
    }
  }

  const fresh = emptyStore();
  saveThreadStore(fresh);
  return fresh;
}

export function saveThreadStore(store: ThreadStore): void {
  writeSessionJson(THREAD_STORAGE_KEY, store);
}

/** Newest first, capped — an unbounded list would grow forever in storage. */
export function sortAndCap(threads: ThreadRecord[]): ThreadRecord[] {
  return [...threads].sort((a, b) => b.lastActiveAt - a.lastActiveAt).slice(0, MAX_TRACKED_THREADS);
}

export function patchThread(
  store: ThreadStore,
  threadId: string,
  changes: Partial<ThreadRecord>,
): ThreadStore {
  return {
    ...store,
    threads: store.threads.map((thread) =>
      thread.threadId === threadId ? { ...thread, ...changes } : thread,
    ),
  };
}

export function findThread(store: ThreadStore, threadId: string): ThreadRecord | undefined {
  return store.threads.find((thread) => thread.threadId === threadId);
}

/** A conversation is named after its opening message, the way a subject line works. */
export function titleFromMessage(text: string, attachmentName?: string): string {
  const trimmed = text.trim().replace(/\s+/g, ' ');
  if (!trimmed) return attachmentName ?? 'New conversation';
  return trimmed.length > 60 ? `${trimmed.slice(0, 57)}…` : trimmed;
}
