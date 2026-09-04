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

/** Cross-tab notification for a storage key, mirrored back into React state. */
export function subscribeToKey(key: string, onChange: () => void): () => void {
  const handler = (event: StorageEvent) => {
    if (event.key === null || event.key === key) onChange();
  };
  window.addEventListener('storage', handler);
  return () => window.removeEventListener('storage', handler);
}
