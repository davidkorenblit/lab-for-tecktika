import { api } from './apiClient';
import { parseSseStream } from '@/lib/sse';
import { uid } from '@/lib/format';
import type {
  ChatHistoryResponse,
  ChatMessage,
  Citation,
  ConfirmationRequest,
  FileAction,
  MessageAttachment,
} from '@/types';

/* --------------------------------- history -------------------------------- */

export async function fetchChatHistory(conversationId?: string): Promise<ChatHistoryResponse> {
  const query = conversationId ? `?conversationId=${encodeURIComponent(conversationId)}` : '';
  const payload = await api.get<unknown>(`/api/chat/history${query}`);
  return normaliseHistory(payload);
}

function normaliseHistory(payload: unknown): ChatHistoryResponse {
  const raw = Array.isArray(payload)
    ? payload
    : ((payload as { messages?: unknown[] } | null)?.messages ?? []);
  const conversationId = Array.isArray(payload)
    ? undefined
    : (payload as { conversationId?: string } | null)?.conversationId;

  return {
    conversationId,
    messages: (raw as unknown[]).map(normaliseMessage).filter((m): m is ChatMessage => m !== null),
  };
}

function normaliseMessage(raw: unknown): ChatMessage | null {
  if (!raw || typeof raw !== 'object') return null;
  const record = raw as Record<string, unknown>;
  const role = String(record.role ?? 'assistant') as ChatMessage['role'];

  return {
    id: String(record.id ?? record.messageId ?? uid('msg')),
    role: role === 'user' || role === 'system' ? role : 'assistant',
    content: String(record.content ?? record.text ?? ''),
    createdAt: String(record.createdAt ?? record.timestamp ?? new Date().toISOString()),
    status: 'complete',
    citations: normaliseCitations(record.citations ?? record.sources),
    attachments: normaliseAttachments(record.attachments ?? record.files),
    confirmation: normaliseConfirmation(record.confirmation ?? record.pendingConfirmation),
    jobIds: Array.isArray(record.jobIds) ? record.jobIds.map(String) : undefined,
  };
}

/** Attachments echoed back by the history endpoint, so they survive a refresh. */
function normaliseAttachments(raw: unknown): MessageAttachment[] | undefined {
  if (!Array.isArray(raw) || raw.length === 0) return undefined;
  const attachments = raw
    .map((item): MessageAttachment | null => {
      if (typeof item === 'string') return { fileName: item };
      if (!item || typeof item !== 'object') return null;
      const record = item as Record<string, unknown>;
      const fileName = asString(record.fileName ?? record.name);
      if (!fileName) return null;
      return {
        fileId: asString(record.fileId ?? record.id),
        fileName,
        size: typeof record.size === 'number' ? record.size : undefined,
        blobPath: asString(record.blobPath ?? record.path),
      };
    })
    .filter((item): item is MessageAttachment => item !== null);

  return attachments.length > 0 ? attachments : undefined;
}

export function normaliseCitations(raw: unknown): Citation[] | undefined {
  if (!Array.isArray(raw) || raw.length === 0) return undefined;
  return raw.map((item, index) => {
    const record = (item ?? {}) as Record<string, unknown>;
    const fileName = asString(record.fileName ?? record.filename ?? record.name);
    return {
      id: String(record.id ?? record.chunkId ?? `citation-${index}`),
      title: asString(record.title ?? record.name) ?? fileName ?? `Source ${index + 1}`,
      url: asString(record.url ?? record.webUrl ?? record.link),
      fileName,
      page: typeof record.page === 'number' ? record.page : undefined,
      snippet: asString(record.snippet ?? record.excerpt ?? record.content),
      score: typeof record.score === 'number' ? record.score : undefined,
    };
  });
}

export function normaliseConfirmation(raw: unknown): ConfirmationRequest | undefined {
  if (!raw || typeof raw !== 'object') return undefined;
  const record = raw as Record<string, unknown>;
  const confirmationId = asString(record.confirmationId ?? record.id);
  if (!confirmationId) return undefined;

  const action = String(record.action ?? 'unknown').toLowerCase() as FileAction;
  const rawFiles = Array.isArray(record.files) ? record.files : [record.file].filter(Boolean);

  const files = rawFiles.map((item) => {
    if (typeof item === 'string') return { name: item };
    const file = (item ?? {}) as Record<string, unknown>;
    return {
      name: asString(file.name ?? file.fileName ?? file.path) ?? 'unknown file',
      path: asString(file.path),
      size: typeof file.size === 'number' ? file.size : undefined,
      url: asString(file.url ?? file.webUrl),
      version: asString(file.version),
    };
  });

  return {
    confirmationId,
    action: ['upload', 'replace', 'update', 'delete', 'move'].includes(action) ? action : 'unknown',
    summary: asString(record.summary ?? record.message ?? record.prompt) ?? 'Confirm this action?',
    files,
    // Anything that can destroy or overwrite content defaults to destructive, so
    // an unrecognised action still gets the strict confirmation UI.
    destructive: typeof record.destructive === 'boolean' ? record.destructive : action !== 'upload',
    expiresAt: asString(record.expiresAt),
  };
}

function asString(value: unknown): string | undefined {
  return typeof value === 'string' && value.length > 0 ? value : undefined;
}

/* ---------------------------------- stream -------------------------------- */

export type ChatStreamEvent =
  | { type: 'start'; messageId?: string; conversationId?: string }
  | { type: 'delta'; text: string }
  | { type: 'citations'; citations: Citation[] }
  | { type: 'confirmation'; confirmation: ConfirmationRequest }
  | { type: 'job'; jobId: string; action: FileAction; label?: string; fileName?: string }
  | { type: 'error'; message: string }
  | { type: 'done'; messageId?: string; conversationId?: string };

export interface SendMessageArgs {
  message: string;
  conversationId?: string;
  /** Files already staged in storage that this turn is about. */
  attachments?: MessageAttachment[];
  signal?: AbortSignal;
  onEvent: (event: ChatStreamEvent) => void;
}

/**
 * POSTs a message and consumes the SSE response.
 *
 * Resolves when the stream ends. Aborting via `signal` resolves rather than
 * throwing, because a user-cancelled turn is not an error.
 */
export async function streamChatMessage({
  message,
  conversationId,
  attachments,
  signal,
  onEvent,
}: SendMessageArgs): Promise<void> {
  let response: Response;
  try {
    response = await api.raw('/api/chat/message', {
      method: 'POST',
      body: {
        message,
        conversationId,
        stream: true,
        attachments: attachments?.length ? attachments : undefined,
      },
      headers: { Accept: 'text/event-stream' },
      signal,
    });
  } catch (error) {
    if (signal?.aborted) return;
    throw error;
  }

  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    throw new Error(detail || `Chat request failed (${response.status})`);
  }
  if (!response.body) throw new Error('Chat response did not include a stream body');

  // A backend that answers a stream request with plain JSON still works.
  const contentType = response.headers.get('content-type') ?? '';
  if (!contentType.includes('text/event-stream')) {
    const payload = await response.json().catch(() => null);
    emitFromPayload(payload, onEvent);
    onEvent({ type: 'done' });
    return;
  }

  try {
    for await (const frame of parseSseStream(response.body, signal)) {
      if (signal?.aborted) return;
      if (frame.data === '[DONE]') {
        onEvent({ type: 'done' });
        return;
      }

      const payload = safeJsonParse(frame.data);
      const event = toStreamEvent(frame.event, payload, frame.data);
      if (event) onEvent(event);
      if (event?.type === 'done') return;
    }
  } catch (error) {
    if (signal?.aborted) return;
    throw error;
  }
}

function toStreamEvent(eventName: string, payload: unknown, rawData: string): ChatStreamEvent | null {
  const record = (payload && typeof payload === 'object' ? payload : {}) as Record<string, unknown>;
  // Typed frames win; otherwise fall back to a type field inside the payload.
  const name = (eventName === 'message' ? String(record.type ?? 'delta') : eventName).toLowerCase();

  switch (name) {
    case 'start':
    case 'message_start':
      return {
        type: 'start',
        messageId: asString(record.messageId ?? record.id),
        conversationId: asString(record.conversationId ?? record.threadId),
      };

    case 'delta':
    case 'token':
    case 'text':
    case 'content':
    case 'chunk': {
      const text =
        asString(record.delta) ??
        asString(record.text) ??
        asString(record.content) ??
        (payload === null ? rawData : '');
      return text ? { type: 'delta', text } : null;
    }

    case 'citation':
    case 'citations':
    case 'sources': {
      const citations = normaliseCitations(
        Array.isArray(payload) ? payload : (record.citations ?? record.sources ?? [payload]),
      );
      return citations ? { type: 'citations', citations } : null;
    }

    case 'confirmation':
    case 'confirmation_required':
    case 'confirm': {
      const confirmation = normaliseConfirmation(record.confirmation ?? payload);
      return confirmation ? { type: 'confirmation', confirmation } : null;
    }

    case 'job':
    case 'job_started': {
      const job = (record.job ?? payload) as Record<string, unknown>;
      const jobId = asString(job.jobId ?? job.id);
      if (!jobId) return null;
      return {
        type: 'job',
        jobId,
        action: (asString(job.action) as FileAction) ?? 'unknown',
        label: asString(job.label ?? job.summary),
        fileName: asString(job.fileName ?? job.name),
      };
    }

    case 'error':
      return { type: 'error', message: asString(record.message ?? record.error) ?? 'Stream error' };

    case 'end':
    case 'done':
    case 'complete':
      return {
        type: 'done',
        messageId: asString(record.messageId ?? record.id),
        conversationId: asString(record.conversationId ?? record.threadId),
      };

    default:
      return null;
  }
}

/** Non-streaming fallback: turn one JSON reply into the same event sequence. */
function emitFromPayload(payload: unknown, onEvent: (event: ChatStreamEvent) => void): void {
  const message =
    normaliseMessage(payload) ?? normaliseMessage((payload as { message?: unknown })?.message);
  if (!message) return;
  if (message.content) onEvent({ type: 'delta', text: message.content });
  if (message.citations) onEvent({ type: 'citations', citations: message.citations });
  if (message.confirmation) onEvent({ type: 'confirmation', confirmation: message.confirmation });
}

function safeJsonParse(value: string): unknown {
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}
