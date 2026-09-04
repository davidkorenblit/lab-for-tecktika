/**
 * Minimal Server-Sent Events reader.
 *
 * `EventSource` can only issue GETs and cannot set an Authorization header, so
 * the chat stream is read from a `fetch` POST body instead. This parses the
 * wire format: frames separated by a blank line, each with optional `event:`,
 * `id:` and one or more `data:` lines.
 */
export interface SseFrame {
  event: string;
  data: string;
  id?: string;
  retry?: number;
}

export async function* parseSseStream(
  body: ReadableStream<Uint8Array>,
  signal?: AbortSignal,
): AsyncGenerator<SseFrame> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  const abortHandler = () => void reader.cancel().catch(() => undefined);
  signal?.addEventListener('abort', abortHandler);

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Frames end with a blank line; \r\n is legal too.
      let boundary = findFrameBoundary(buffer);
      while (boundary !== -1) {
        const raw = buffer.slice(0, boundary.index);
        buffer = buffer.slice(boundary.index + boundary.length);
        const frame = parseFrame(raw);
        if (frame) yield frame;
        boundary = findFrameBoundary(buffer);
      }
    }

    // A server that closes without a trailing blank line still gets parsed.
    buffer += decoder.decode();
    const tail = parseFrame(buffer);
    if (tail) yield tail;
  } finally {
    signal?.removeEventListener('abort', abortHandler);
    reader.releaseLock();
  }
}

type Boundary = { index: number; length: number } | -1;

function findFrameBoundary(buffer: string): Boundary {
  const lf = buffer.indexOf('\n\n');
  const crlf = buffer.indexOf('\r\n\r\n');
  if (lf === -1 && crlf === -1) return -1;
  if (crlf !== -1 && (lf === -1 || crlf < lf)) return { index: crlf, length: 4 };
  return { index: lf, length: 2 };
}

function parseFrame(raw: string): SseFrame | null {
  const lines = raw.split(/\r?\n/);
  const dataLines: string[] = [];
  let event = 'message';
  let id: string | undefined;
  let retry: number | undefined;

  for (const line of lines) {
    if (!line || line.startsWith(':')) continue; // comment / keep-alive ping
    const colon = line.indexOf(':');
    const field = colon === -1 ? line : line.slice(0, colon);
    // A single leading space after the colon is part of the framing, not data.
    let value = colon === -1 ? '' : line.slice(colon + 1);
    if (value.startsWith(' ')) value = value.slice(1);

    switch (field) {
      case 'event':
        event = value;
        break;
      case 'data':
        dataLines.push(value);
        break;
      case 'id':
        id = value;
        break;
      case 'retry': {
        const parsed = Number(value);
        if (!Number.isNaN(parsed)) retry = parsed;
        break;
      }
      default:
        break;
    }
  }

  if (dataLines.length === 0 && event === 'message') return null;
  return { event, data: dataLines.join('\n'), id, retry };
}
