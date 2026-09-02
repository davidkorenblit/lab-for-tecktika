import { useCallback, useState } from 'react';
import type { ConfirmationRequest } from '@/types';

export interface QueuedConfirmation {
  messageId: string;
  confirmation: ConfirmationRequest;
}

/**
 * One destructive confirmation on screen at a time.
 *
 * The agent can raise two in a row — "replace A?" immediately followed by
 * "delete B?" — and rendering both meant two `aria-modal` dialogs fighting over
 * the focus trap, with the second stacked on the first. Requests queue instead,
 * and the next one opens only after the current is answered or dismissed.
 */
export function useConfirmationQueue() {
  const [queue, setQueue] = useState<QueuedConfirmation[]>([]);

  const enqueue = useCallback((item: QueuedConfirmation) => {
    setQueue((current) =>
      current.some((entry) => entry.confirmation.confirmationId === item.confirmation.confirmationId)
        ? current
        : [...current, item],
    );
  }, []);

  /** Drops the open request, whether it was answered or cancelled. */
  const resolveCurrent = useCallback(() => {
    setQueue((current) => current.slice(1));
  }, []);

  return {
    current: queue[0] ?? null,
    /** Shown in the dialog so the user knows more decisions are coming. */
    waiting: Math.max(0, queue.length - 1),
    enqueue,
    resolveCurrent,
  };
}
