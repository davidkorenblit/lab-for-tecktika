import { useEffect, useState } from 'react';
import { isExpired } from '@/lib/confirmations';

/** setTimeout saturates past ~24.8 days and fires immediately. */
const MAX_TIMEOUT_MS = 2_147_483_647;

/**
 * Tracks whether a confirmation's window has closed.
 *
 * Schedules a single timeout for the exact moment of expiry rather than polling,
 * so a dialog left open goes stale on its own without a ticking interval behind
 * every confirmation on screen.
 */
export function useExpiry(expiresAt: string | undefined): boolean {
  const [expired, setExpired] = useState(() => isExpired(expiresAt));

  useEffect(() => {
    if (!expiresAt) {
      setExpired(false);
      return;
    }

    const parsed = Date.parse(expiresAt);
    if (Number.isNaN(parsed)) {
      setExpired(false);
      return;
    }

    const remaining = parsed - Date.now();
    if (remaining <= 0) {
      setExpired(true);
      return;
    }

    setExpired(false);
    const timer = window.setTimeout(() => setExpired(true), Math.min(remaining, MAX_TIMEOUT_MS));
    return () => window.clearTimeout(timer);
  }, [expiresAt]);

  return expired;
}
