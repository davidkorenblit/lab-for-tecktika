// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from 'vitest';
import { applyStoredResolutions, isExpired, recordResolution } from './confirmations';
import type { ChatMessage } from '@/types';

function messageWithConfirmation(confirmationId: string): ChatMessage {
  return {
    id: 'm1',
    role: 'assistant',
    content: 'Delete Q3-report.pdf?',
    createdAt: new Date().toISOString(),
    confirmation: {
      confirmationId,
      action: 'delete',
      summary: 'Delete it',
      files: [{ name: 'Q3-report.pdf' }],
      destructive: true,
    },
  };
}

describe('confirmation resolutions', () => {
  beforeEach(() => window.localStorage.clear());

  it('re-attaches a decision after a reload so it is not offered twice', () => {
    recordResolution('c1', { decision: 'confirmed', at: '2026-09-02T10:00:00Z', jobId: 'job_7' });

    const [message] = applyStoredResolutions([messageWithConfirmation('c1')]);

    expect(message.confirmationResolution).toMatchObject({
      decision: 'confirmed',
      jobId: 'job_7',
    });
  });

  it('leaves an unrelated confirmation open', () => {
    recordResolution('c1', { decision: 'confirmed', at: '2026-09-02T10:00:00Z' });
    const [message] = applyStoredResolutions([messageWithConfirmation('c2')]);
    expect(message.confirmationResolution).toBeUndefined();
  });

  it('does not overwrite a decision already on the message', () => {
    recordResolution('c1', { decision: 'confirmed', at: '2026-09-02T10:00:00Z' });
    const declined = {
      ...messageWithConfirmation('c1'),
      confirmationResolution: { decision: 'declined' as const, at: '2026-09-02T11:00:00Z' },
    };
    expect(applyStoredResolutions([declined])[0].confirmationResolution?.decision).toBe('declined');
  });

  it('survives unreadable storage without throwing', () => {
    window.localStorage.setItem('ai-agent-chat.confirmations.v1', 'not json');
    expect(() => applyStoredResolutions([messageWithConfirmation('c1')])).not.toThrow();
  });
});

describe('isExpired', () => {
  const now = Date.parse('2026-09-02T12:00:00Z');

  it('is false when the backend sets no expiry', () => {
    expect(isExpired(undefined, now)).toBe(false);
  });

  it('is false for an unparseable value rather than locking the button', () => {
    expect(isExpired('whenever', now)).toBe(false);
  });

  it('tracks the boundary', () => {
    expect(isExpired('2026-09-02T12:00:01Z', now)).toBe(false);
    expect(isExpired('2026-09-02T11:59:59Z', now)).toBe(true);
  });
});
