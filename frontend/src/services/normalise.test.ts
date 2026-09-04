import { describe, expect, it } from 'vitest';
import { normaliseCitations, normaliseConfirmation } from './chat';
import { normaliseJobStatus } from './jobs';

/**
 * The normalisers are the client's half of the contract in API.md: they decide
 * what shapes the backend is allowed to send. If one of these changes, the
 * document is wrong.
 */

describe('normaliseJobStatus', () => {
  it.each([
    ['completed', 'succeeded'],
    ['success', 'succeeded'],
    ['done', 'succeeded'],
    ['in_progress', 'running'],
    ['processing', 'running'],
    ['faulted', 'failed'],
    ['canceled', 'cancelled'],
    ['something-else', 'queued'],
  ])('maps %s to %s', (input, expected) => {
    expect(normaliseJobStatus('j1', { state: input }).state).toBe(expected);
  });

  it('accepts status as an alias for state', () => {
    expect(normaliseJobStatus('j1', { status: 'running' }).state).toBe('running');
  });

  it('scales fractional progress to a percentage', () => {
    expect(normaliseJobStatus('j1', { progress: 0.45 }).progress).toBe(45);
    expect(normaliseJobStatus('j1', { progress: 45 }).progress).toBe(45);
    expect(normaliseJobStatus('j1', { progress: 140 }).progress).toBe(100);
  });

  it('falls back to the requested id when the payload omits one', () => {
    expect(normaliseJobStatus('j1', {}).jobId).toBe('j1');
  });
});

describe('normaliseConfirmation', () => {
  it('drops a confirmation with no id — it could never be answered', () => {
    expect(normaliseConfirmation({ action: 'delete', files: ['a.pdf'] })).toBeUndefined();
  });

  it('treats an unrecognised action as destructive', () => {
    const result = normaliseConfirmation({ id: 'c1', action: 'purge', files: ['a.pdf'] });
    expect(result?.action).toBe('unknown');
    expect(result?.destructive).toBe(true);
  });

  it('defaults upload to non-destructive and delete to destructive', () => {
    expect(normaliseConfirmation({ id: 'c1', action: 'upload' })?.destructive).toBe(false);
    expect(normaliseConfirmation({ id: 'c1', action: 'delete' })?.destructive).toBe(true);
  });

  it('accepts a bare string as a file name', () => {
    const result = normaliseConfirmation({ id: 'c1', action: 'delete', files: ['Q3.pdf'] });
    expect(result?.files).toEqual([{ name: 'Q3.pdf' }]);
  });

  it('accepts a single file under the singular key', () => {
    const result = normaliseConfirmation({ id: 'c1', action: 'delete', file: { name: 'Q3.pdf' } });
    expect(result?.files.map((f) => f.name)).toEqual(['Q3.pdf']);
  });

  it('honours an explicit destructive flag over the action default', () => {
    expect(normaliseConfirmation({ id: 'c1', action: 'delete', destructive: false })?.destructive).toBe(
      false,
    );
  });
});

describe('normaliseCitations', () => {
  it('returns undefined for an empty list so nothing renders', () => {
    expect(normaliseCitations([])).toBeUndefined();
    expect(normaliseCitations(null)).toBeUndefined();
  });

  it('accepts the documented aliases', () => {
    const [citation] = normaliseCitations([
      { chunkId: 'c9', filename: 'vendor.pdf', webUrl: 'https://x', excerpt: 'text', page: 11 },
    ])!;
    expect(citation).toMatchObject({
      id: 'c9',
      fileName: 'vendor.pdf',
      url: 'https://x',
      snippet: 'text',
      page: 11,
    });
  });

  it('falls back to a positional title when nothing names the source', () => {
    expect(normaliseCitations([{}])![0].title).toBe('Source 1');
  });
});
