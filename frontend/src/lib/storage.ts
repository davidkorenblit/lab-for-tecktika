/**
 * localStorage helpers that never throw.
 *
 * Private windows and hardened browser settings can make the accessor itself
 * throw, and a failed job-registry read must not take the chat down with it.
 */
export function readJson<T>(key: string, fallback: T): T {
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export function writeJson(key: string, value: unknown): void {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* quota exceeded or storage blocked — the UI degrades to in-memory only */
  }
}

export function removeKey(key: string): void {
  try {
    window.localStorage.removeItem(key);
  } catch {
    /* ignore */
  }
}

/**
 * The same helpers against sessionStorage, for state that should last exactly
 * as long as the browsing session: a refresh keeps it, closing the tab does
 * not. That is what makes each sign-in start on a clean conversation.
 */
export function readSessionJson<T>(key: string, fallback: T): T {
  try {
    const raw = window.sessionStorage.getItem(key);
    if (!raw) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export function writeSessionJson(key: string, value: unknown): void {
  try {
    window.sessionStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* quota exceeded or storage blocked — the UI degrades to in-memory only */
  }
}

/** Cross-tab notification for a storage key, mirrored back into React state. */
export function subscribeToKey(key: string, onChange: () => void): () => void {
  const handler = (event: StorageEvent) => {
    if (event.key === null || event.key === key) onChange();
  };
  window.addEventListener('storage', handler);
  return () => window.removeEventListener('storage', handler);
}
