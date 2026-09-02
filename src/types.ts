/**
 * Shared contracts between the UI and the backend.
 *
 * Anything marked "tolerant" is normalised in the service layer, because the
 * agent backend is free to send a slightly looser shape than the UI wants.
 */

/* ---------------------------------- auth --------------------------------- */

/** Azure Static Web Apps `/.auth/me` client principal. */
export interface ClientPrincipal {
  identityProvider: string;
  userId: string;
  userDetails: string;
  userRoles: string[];
  claims?: Array<{ typ: string; val: string }>;
}

export interface AuthSession {
  principal: ClientPrincipal | null;
  /** Bearer token attached to every API call. Null when only cookie auth is available. */
  token: string | null;
  /** Epoch ms. Used to refresh before the token goes stale. */
  expiresAt: number | null;
}

/* ---------------------------------- chat --------------------------------- */

export type ChatRole = 'user' | 'assistant' | 'system';

export interface Citation {
  id: string;
  /** Human readable label, usually the SharePoint file name. */
  title: string;
  /** Deep link into SharePoint, when the backend can build one. */
  url?: string;
  fileName?: string;
  page?: number;
  snippet?: string;
  score?: number;
}

export type MessageStatus = 'streaming' | 'complete' | 'error';

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  createdAt: string;
  status?: MessageStatus;
  citations?: Citation[];
  /** Present when the agent wants an explicit yes/no before acting. */
  confirmation?: ConfirmationRequest;
  /** Present when this turn kicked off background work. */
  jobIds?: string[];
  /** Set once the user has answered the confirmation attached to this message. */
  confirmationResolution?: {
    decision: 'confirmed' | 'declined';
    at: string;
    jobId?: string;
  };
  error?: string;
}

export interface ChatHistoryResponse {
  messages: ChatMessage[];
  conversationId?: string;
}

/* ------------------------------ confirmations ----------------------------- */

export type FileAction = 'upload' | 'replace' | 'update' | 'delete' | 'move' | 'unknown';

export interface AffectedFile {
  /** Always rendered verbatim in the confirmation prompt. */
  name: string;
  path?: string;
  size?: number;
  url?: string;
  version?: string;
}

export interface ConfirmationRequest {
  confirmationId: string;
  action: FileAction;
  /** Agent-authored explanation of what is about to happen. */
  summary: string;
  /** Never empty for destructive actions — the UI names these files. */
  files: AffectedFile[];
  destructive: boolean;
  expiresAt?: string;
}

export interface ConfirmActionResponse {
  jobId?: string;
  status?: string;
  message?: string;
}

/* ----------------------------------- jobs --------------------------------- */

export type JobState = 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled';

export interface JobStatus {
  jobId: string;
  state: JobState;
  /** 0-100 when the backend reports it. */
  progress?: number;
  message?: string;
  error?: string;
  fileName?: string;
  updatedAt?: string;
  result?: unknown;
}

/** The slice of a job we persist to localStorage so it survives a refresh. */
export interface TrackedJob {
  jobId: string;
  action: FileAction;
  /** Short label shown in the job tray, e.g. "Delete Q3-report.pdf". */
  label: string;
  fileName?: string;
  startedAt: number;
  /** Last state we saw, so a refresh renders something before the first poll. */
  lastState?: JobState;
  lastProgress?: number;
  lastMessage?: string;
  /** Terminal jobs the user has acknowledged; kept out of the active list. */
  dismissedAt?: number;
}

/* ---------------------------------- upload -------------------------------- */

export interface UploadUrlRequest {
  fileName: string;
  contentType: string;
  size: number;
  /** Set once the user has confirmed an overwrite. */
  overwrite?: boolean;
}

export interface UploadUrlResponse {
  /** Presigned (SAS) URL the browser PUTs the bytes to. */
  uploadUrl: string;
  fileId?: string;
  blobPath?: string;
  expiresAt?: string;
  /**
   * Backend detected an existing file with the same name. The UI must confirm
   * the overwrite — naming the file — before any bytes are sent.
   */
  requiresConfirmation?: ConfirmationRequest;
}

export type UploadPhase =
  | 'idle'
  | 'requesting-url'
  | 'awaiting-confirmation'
  | 'uploading'
  | 'finalizing'
  | 'done'
  | 'error'
  | 'cancelled';

export interface UploadTask {
  id: string;
  fileName: string;
  size: number;
  phase: UploadPhase;
  /** 0-100, bytes actually acknowledged by Azure Blob Storage. */
  progress: number;
  error?: string;
  jobId?: string;
  confirmation?: ConfirmationRequest;
}
