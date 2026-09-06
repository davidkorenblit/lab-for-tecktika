import { CONFIRMATION_RESOLUTION_MAX_AGE_MS, CONFIRMATION_RESOLUTIONS_KEY } from '@/config';
import { readJson, writeJson } from '@/lib/storage';
import type { ChatMessage } from '@/types';

/**
 * Answers the user has already given to confirmations.
 *
 * The decision used to live only in the React Query cache, so a refresh
 * re-rendered an answered confirmation as still actionable and invited a second
 * delete. The server should be idempotent regardless — see API.md §3.4 — but the
 * UI must not offer an action the user has already taken.
 *
 * Keyed by `confirmationId`, which the backend issues, so the record survives
 * whatever the client does with its own message ids.
 */
type StoredResolution = NonNullable<ChatMessage['confirmationResolution']> & { savedAt: number };
type ResolutionMap = Record<string, StoredResolution>;

function load(): ResolutionMap {
  const stored = readJson<ResolutionMap | null>(CONFIRMATION_RESOLUTIONS_KEY, null);
  return stored && typeof stored === 'object' ? stored : {};
}

export function recordResolution(
  confirmationId: string,
  resolution: NonNullable<ChatMessage['confirmationResolution']>,
): void {
  const now = Date.now();
  const map = load();
  map[confirmationId] = { ...resolution, savedAt: now };

  // Prune on write; there is no other moment this map is visited.
  for (const [id, entry] of Object.entries(map)) {
    if (now - (entry.savedAt ?? 0) > CONFIRMATION_RESOLUTION_MAX_AGE_MS) delete map[id];
  }

  writeJson(CONFIRMATION_RESOLUTIONS_KEY, map);
}

/** Re-attaches known decisions to freshly loaded history. */
export function applyStoredResolutions(messages: ChatMessage[]): ChatMessage[] {
  const map = load();
  if (Object.keys(map).length === 0) return messages;

  return messages.map((message) => {
    const confirmationId = message.confirmation?.confirmationId;
    if (!confirmationId || message.confirmationResolution) return message;
    const stored = map[confirmationId];
    if (!stored) return message;
    return {
      ...message,
      confirmationResolution: { decision: stored.decision, at: stored.at, jobId: stored.jobId },
    };
  });
}

/** True once the backend's confirmation window has passed. */
export function isExpired(expiresAt: string | undefined, now = Date.now()): boolean {
  if (!expiresAt) return false;
  const parsed = Date.parse(expiresAt);
  return !Number.isNaN(parsed) && parsed <= now;
}
