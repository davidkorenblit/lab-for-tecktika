import { api } from './apiClient';
import type { JobState, JobStatus } from '@/types';

const TERMINAL_STATES: JobState[] = ['succeeded', 'failed', 'cancelled'];

export function isTerminal(state: JobState | undefined): boolean {
  return state !== undefined && TERMINAL_STATES.includes(state);
}

export async function fetchJobStatus(jobId: string): Promise<JobStatus> {
  const payload = await api.get<unknown>(`/api/jobs/${encodeURIComponent(jobId)}/status`);
  return normaliseJobStatus(jobId, payload);
}

export function normaliseJobStatus(jobId: string, payload: unknown): JobStatus {
  const record = (payload && typeof payload === 'object' ? payload : {}) as Record<string, unknown>;
  const rawState = String(record.state ?? record.status ?? 'queued').toLowerCase();

  return {
    jobId: String(record.jobId ?? record.id ?? jobId),
    state: mapState(rawState),
    progress: typeof record.progress === 'number' ? clampPercent(record.progress) : undefined,
    message: asString(record.message ?? record.detail ?? record.statusMessage),
    error: asString(record.error ?? record.errorMessage),
    fileName: asString(record.fileName ?? record.name),
    updatedAt: asString(record.updatedAt ?? record.completedAt ?? record.timestamp),
    result: record.result,
  };
}

/** Maps the state vocabularies a job runner might use onto our five states. */
function mapState(value: string): JobState {
  switch (value) {
    case 'succeeded':
    case 'success':
    case 'completed':
    case 'complete':
    case 'done':
      return 'succeeded';
    case 'failed':
    case 'error':
    case 'faulted':
      return 'failed';
    case 'cancelled':
    case 'canceled':
    case 'aborted':
      return 'cancelled';
    case 'running':
    case 'inprogress':
    case 'in_progress':
    case 'processing':
    case 'started':
      return 'running';
    default:
      return 'queued';
  }
}

function clampPercent(value: number): number {
  const scaled = value > 0 && value <= 1 ? value * 100 : value;
  return Math.max(0, Math.min(100, Math.round(scaled)));
}

function asString(value: unknown): string | undefined {
  return typeof value === 'string' && value.length > 0 ? value : undefined;
}
