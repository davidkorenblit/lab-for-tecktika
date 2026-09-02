import { api } from './apiClient';
import type {
  ConfirmActionResponse,
  ConfirmationRequest,
  UploadUrlRequest,
  UploadUrlResponse,
} from '@/types';

/**
 * Asks the API for a short-lived SAS URL and a handle for the staged blob.
 *
 * Nothing is decided here: the bytes land in staging, and the `fileId` travels
 * with the chat message so the agent can work out whether this is a new
 * document, a replacement, or an update — and ask before acting.
 */
export async function requestUploadUrl(request: UploadUrlRequest): Promise<UploadUrlResponse> {
  const payload = await api.post<unknown>('/api/files/upload-url', request);
  const record = (payload ?? {}) as Record<string, unknown>;

  const uploadUrl = asString(record.uploadUrl ?? record.url ?? record.sasUrl);
  if (!uploadUrl) throw new Error('Backend did not return an upload URL');

  return {
    uploadUrl,
    fileId: asString(record.fileId ?? record.id),
    blobPath: asString(record.blobPath ?? record.path ?? record.blobName),
    expiresAt: asString(record.expiresAt),
  };
}

export interface ConfirmActionInput {
  /**
   * Issued by the backend on a `confirmation` frame. Never synthesised on the
   * client — a made-up id would let the UI approve an action the server never
   * proposed.
   */
  confirmationId: string;
  confirmed: boolean;
  /** Echoed back so the server can verify the user saw the right files. */
  files?: string[];
  action?: string;
}

/**
 * Sends the user's explicit yes/no. Returns a jobId when the backend accepted
 * the action and queued the work.
 */
export async function confirmAction(input: ConfirmActionInput): Promise<ConfirmActionResponse> {
  const payload = await api.post<unknown>('/api/files/confirm-action', input);
  const record = (payload ?? {}) as Record<string, unknown>;
  return {
    jobId: asString(record.jobId ?? record.id),
    status: asString(record.status ?? record.state),
    message: asString(record.message),
  };
}

/** Every file named in a confirmation, for prompt text and job labels. */
export function fileNames(confirmation: ConfirmationRequest): string[] {
  return confirmation.files.map((file) => file.name);
}

function asString(value: unknown): string | undefined {
  return typeof value === 'string' && value.length > 0 ? value : undefined;
}
