import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { useQueries } from '@tanstack/react-query';
import {
  JOBS_STORAGE_KEY,
  JOB_POLL_INTERVAL_MS,
  JOB_POLL_MAX_INTERVAL_MS,
  JOB_RETENTION_MS,
} from '@/config';
import { queryKeys } from '@/lib/queryClient';
import { readJson, subscribeToKey, writeJson } from '@/lib/storage';
import { fetchJobStatus, isTerminal } from '@/services/jobs';
import type { JobStatus, TrackedJob } from '@/types';

/**
 * Background job registry.
 *
 * File operations run server-side and can outlive the page. The jobId is
 * written to localStorage the moment a job starts, so a refresh (or a second
 * tab) picks the poll back up and the user still sees the outcome. Polling
 * lives here rather than in the chat, which is why the chat never blocks on it.
 */

interface JobsContextValue {
  jobs: TrackedJob[];
  activeJobs: TrackedJob[];
  finishedJobs: TrackedJob[];
  statuses: Record<string, JobStatus>;
  trackJob: (job: TrackedJobInput) => void;
  dismissJob: (jobId: string) => void;
  dismissFinished: () => void;
  getStatus: (jobId: string) => JobStatus | undefined;
}

export interface TrackedJobInput {
  jobId: string;
  action: TrackedJob['action'];
  label: string;
  fileName?: string;
}

const JobsContext = createContext<JobsContextValue | null>(null);

function loadJobs(): TrackedJob[] {
  const stored = readJson<TrackedJob[]>(JOBS_STORAGE_KEY, []);
  if (!Array.isArray(stored)) return [];
  const cutoff = Date.now() - JOB_RETENTION_MS;
  return stored.filter(
    (job) =>
      job &&
      typeof job.jobId === 'string' &&
      // Keep everything still in flight; drop stale finished jobs.
      (!isTerminal(job.lastState) || job.startedAt > cutoff),
  );
}

export function JobsProvider({ children }: { children: ReactNode }) {
  const [jobs, setJobs] = useState<TrackedJob[]>(loadJobs);

  // Persist on every change and mirror updates made by other tabs.
  useEffect(() => {
    writeJson(JOBS_STORAGE_KEY, jobs);
  }, [jobs]);

  useEffect(() => subscribeToKey(JOBS_STORAGE_KEY, () => setJobs(loadJobs())), []);

  const trackJob = useCallback((input: TrackedJobInput) => {
    setJobs((current) => {
      if (current.some((job) => job.jobId === input.jobId)) return current;
      return [
        ...current,
        {
          jobId: input.jobId,
          action: input.action,
          label: input.label,
          fileName: input.fileName,
          startedAt: Date.now(),
          lastState: 'queued',
        },
      ];
    });
  }, []);

  const dismissJob = useCallback((jobId: string) => {
    setJobs((current) => current.filter((job) => job.jobId !== jobId));
  }, []);

  const dismissFinished = useCallback(() => {
    setJobs((current) => current.filter((job) => !isTerminal(job.lastState)));
  }, []);

  // Only unfinished jobs are polled; finished ones stay in the list, unpolled,
  // until the user dismisses them.
  const pollable = useMemo(() => jobs.filter((job) => !isTerminal(job.lastState)), [jobs]);

  const results = useQueries({
    queries: pollable.map((job) => ({
      queryKey: queryKeys.jobStatus(job.jobId),
      queryFn: () => fetchJobStatus(job.jobId),
      // Back off as a job drags on: 2s at first, easing out to 15s.
      refetchInterval: (query: { state: { data?: JobStatus; dataUpdateCount: number } }) => {
        if (isTerminal(query.state.data?.state)) return false;
        const step = Math.min(query.state.dataUpdateCount, 10);
        return Math.min(
          JOB_POLL_INTERVAL_MS * 1.3 ** step,
          JOB_POLL_MAX_INTERVAL_MS,
        );
      },
      // Indexing a large PDF outlasts a glance at another tab.
      refetchIntervalInBackground: true,
      staleTime: 0,
      gcTime: JOB_RETENTION_MS,
      retry: 3,
    })),
  });

  const statuses = useMemo(() => {
    const map: Record<string, JobStatus> = {};
    for (const result of results) {
      if (result.data) map[result.data.jobId] = result.data;
    }
    return map;
  }, [results]);

  // Fold polled status back into the persisted record so a refresh renders the
  // last known state before the first poll of the new page load returns.
  const lastSyncedRef = useRef('');
  useEffect(() => {
    const fingerprint = JSON.stringify(
      Object.values(statuses).map((s) => [s.jobId, s.state, s.progress, s.message]),
    );
    if (fingerprint === lastSyncedRef.current) return;
    lastSyncedRef.current = fingerprint;

    setJobs((current) => {
      let changed = false;
      const next = current.map((job) => {
        const status = statuses[job.jobId];
        if (!status) return job;
        if (
          job.lastState === status.state &&
          job.lastProgress === status.progress &&
          job.lastMessage === status.message
        ) {
          return job;
        }
        changed = true;
        return {
          ...job,
          lastState: status.state,
          lastProgress: status.progress,
          lastMessage: status.message ?? status.error,
          fileName: job.fileName ?? status.fileName,
        };
      });
      return changed ? next : current;
    });
  }, [statuses]);

  const value = useMemo<JobsContextValue>(() => {
    const activeJobs = jobs.filter((job) => !isTerminal(job.lastState));
    const finishedJobs = jobs.filter((job) => isTerminal(job.lastState));
    return {
      jobs,
      activeJobs,
      finishedJobs,
      statuses,
      trackJob,
      dismissJob,
      dismissFinished,
      getStatus: (jobId: string) => statuses[jobId],
    };
  }, [jobs, statuses, trackJob, dismissJob, dismissFinished]);

  return <JobsContext.Provider value={value}>{children}</JobsContext.Provider>;
}

export function useJobs(): JobsContextValue {
  const context = useContext(JobsContext);
  if (!context) throw new Error('useJobs must be used inside <JobsProvider>');
  return context;
}

/** State for a single job, merging the live poll with the persisted snapshot. */
export function useJob(jobId: string | undefined) {
  const { jobs, statuses } = useJobs();
  if (!jobId) return undefined;
  const tracked = jobs.find((job) => job.jobId === jobId);
  const status = statuses[jobId];
  if (!tracked && !status) return undefined;
  return {
    tracked,
    status:
      status ??
      (tracked
        ? {
            jobId,
            state: tracked.lastState ?? 'queued',
            progress: tracked.lastProgress,
            message: tracked.lastMessage,
          }
        : undefined),
  };
}
