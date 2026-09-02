import { api } from './apiClient';
import { normaliseConfirmation } from './chat';
import type {
  ConfirmActionResponse,
  ConfirmationRequest,
  UploadUrlRequest,
  UploadUrlResponse,
} from '@/types';

/** Step 1 of the upload: ask the API for a short-lived SAS URL. */
export async function requestUploadUrl(request: UploadUrlRequest): Promise<UploadUrlResponse> {
  const payload = await api.post<unknown>('/api/files/upload-url', request);
  const record = (payload ?? {}) as Record<string, unknown>;

  const uploadUrl = String(record.uploadUrl ?? record.url ?? record.sasUrl ?? '');
  const confirmation = normaliseConfirmation(
    record.requiresConfirmation ?? record.confirmation ?? record.pendingConfirmation,
  );

  if (!uploadUrl && !confirmation) {
    throw new Error('Backend did not return an upload URL');
  }

  return {
    uploadUrl,
    fileId: asString(record.fileId ?? record.id),
    blobPath: asString(record.blobPath ?? record.path ?? record.blobName),
    expiresAt: asString(record.expiresAt),
    requiresConfirmation: confirmation,
  };
}

export interface ConfirmActionInput {
  confirmationId: string;
  confirmed: boolean;
  /** Echoed back so the server can verify the user saw the right files. */
  files?: string[];
  fileId?: string;
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

/**
 * Step 3: tell the backend the bytes have landed so it can index the PDF.
 * Reuses confirm-action, which is the endpoint that hands back a jobId.
 */
export async function finalizeUpload(params: {
  fileId?: string;
  fileName: string;
  blobPath?: string;
  confirmationId?: string;
}): Promise<ConfirmActionResponse> {
  return confirmAction({
    confirmationId: params.confirmationId ?? params.fileId ?? params.fileName,
    confirmed: true,
    action: 'upload',
    fileId: params.fileId,
    files: [params.fileName],
  });
}

/** Every file named in a confirmation, for prompt text and job labels. */
export function fileNames(confirmation: ConfirmationRequest): string[] {
  return confirmation.files.map((file) => file.name);
}

function asString(value: unknown): string | undefined {
  return typeof value === 'string' && value.length > 0 ? value : undefined;
}
