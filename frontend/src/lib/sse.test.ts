import { describe, expect, it } from 'vitest';
import { parseSseStream, type SseFrame } from './sse';

/** Feeds the parser exactly the byte boundaries a real network would. */
function streamOf(...chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
}

async function collect(...chunks: string[]): Promise<SseFrame[]> {
  const frames: SseFrame[] = [];
  for await (const frame of parseSseStream(streamOf(...chunks))) frames.push(frame);
  return frames;
}

describe('parseSseStream', () => {
  it('parses a simple typed frame', async () => {
    const frames = await collect('event: delta\ndata: {"delta":"hi"}\n\n');
    expect(frames).toEqual([{ event: 'delta', data: '{"delta":"hi"}', id: undefined, retry: undefined }]);
  });

  it('reassembles a frame split across chunk boundaries', async () => {
    // The split lands mid-field name, mid-value and mid-terminator.
    const frames = await collect('event: de', 'lta\ndata: {"del', 'ta":"hi"}\n', '\n');
    expect(frames).toHaveLength(1);
    expect(frames[0].event).toBe('delta');
    expect(frames[0].data).toBe('{"delta":"hi"}');
  });

  it('handles CRLF framing', async () => {
    const frames = await collect('event: delta\r\ndata: a\r\n\r\nevent: delta\r\ndata: b\r\n\r\n');
    expect(frames.map((f) => f.data)).toEqual(['a', 'b']);
  });

  it('ignores comment keep-alives without emitting a frame', async () => {
    const frames = await collect(': ping\n\n', 'event: delta\ndata: a\n\n', ': ping\n\n');
    expect(frames).toHaveLength(1);
    expect(frames[0].data).toBe('a');
  });

  it('joins multi-line data with newlines', async () => {
    const frames = await collect('data: line one\ndata: line two\n\n');
    expect(frames[0].data).toBe('line one\nline two');
  });

  it('emits a trailing frame when the stream closes without a blank line', async () => {
    const frames = await collect('event: done\ndata: [DONE]');
    expect(frames).toEqual([{ event: 'done', data: '[DONE]', id: undefined, retry: undefined }]);
  });

  it('strips exactly one leading space after the colon', async () => {
    const frames = await collect('data:  two spaces\n\n');
    expect(frames[0].data).toBe(' two spaces');
  });

  it('defaults the event name to message and reads id and retry', async () => {
    const frames = await collect('id: 7\nretry: 3000\ndata: x\n\n');
    expect(frames[0]).toMatchObject({ event: 'message', data: 'x', id: '7', retry: 3000 });
  });

  it('stops when the abort signal fires', async () => {
    const controller = new AbortController();
    const frames: SseFrame[] = [];
    for await (const frame of parseSseStream(
      streamOf('data: a\n\n', 'data: b\n\n'),
      controller.signal,
    )) {
      frames.push(frame);
      controller.abort();
    }
    expect(frames).toHaveLength(1);
  });
});
