import { useState } from 'react';
import { useJobs } from '@/providers/JobsProvider';
import { cx, formatRelative } from '@/lib/format';
import type { JobState, JobStatus, TrackedJob } from '@/types';

/**
 * Floating tray of background operations.
 *
 * Fed entirely from the persisted registry, so a page refresh in the middle of
 * a 5-minute re-index shows the job still running rather than losing it.
 */
export function JobTray() {
  const { jobs, activeJobs, finishedJobs, statuses, dismissJob, dismissFinished } = useJobs();
  const [open, setOpen] = useState(false);

  if (jobs.length === 0) return null;

  const failedCount = finishedJobs.filter((job) => job.lastState === 'failed').length;

  return (
    <div className="pointer-events-none fixed bottom-24 right-4 z-40 flex w-80 max-w-[calc(100vw-2rem)] flex-col items-end gap-2">
      {open && (
        <div className="pointer-events-auto max-h-80 w-full overflow-y-auto rounded-2xl border border-line bg-surface-raised p-2 shadow-xl">
          <div className="flex items-center justify-between px-1.5 py-1">
            <span className="text-xs font-semibold uppercase tracking-wide text-ink-muted">
              Background jobs
            </span>
            {finishedJobs.length > 0 && (
              <button
                type="button"
                onClick={dismissFinished}
                className="text-[11px] text-ink-muted hover:text-brand hover:underline"
              >
                Clear finished
              </button>
            )}
          </div>
          <ul className="flex flex-col gap-1.5">
            {jobs.map((job) => (
              <JobRow
                key={job.jobId}
                job={job}
                status={statuses[job.jobId]}
                onDismiss={() => dismissJob(job.jobId)}
              />
            ))}
          </ul>
        </div>
      )}

      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="pointer-events-auto flex items-center gap-2 rounded-full border border-line bg-surface-raised px-3.5 py-2 text-sm font-medium shadow-lg hover:border-brand/60"
      >
        {activeJobs.length > 0 ? (
          <>
            <span className="size-3.5 animate-spin rounded-full border-2 border-line border-t-brand" />
            {activeJobs.length} running
          </>
        ) : (
          <>
            <StateDot state={failedCount > 0 ? 'failed' : 'succeeded'} />
            {failedCount > 0 ? `${failedCount} failed` : 'Jobs done'}
          </>
        )}
      </button>
    </div>
  );
}

function JobRow({
  job,
  status,
  onDismiss,
}: {
  job: TrackedJob;
  status: JobStatus | undefined;
  onDismiss: () => void;
}) {
  const state: JobState = status?.state ?? job.lastState ?? 'queued';
  const progress = status?.progress ?? job.lastProgress;
  const detail = status?.error ?? status?.message ?? job.lastMessage;

  return (
    <li className="rounded-xl border border-line bg-surface px-2.5 py-2">
      <div className="flex items-start gap-2">
        <StateDot state={state} className="mt-1.5" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium" title={job.label}>
            {job.label}
          </p>
          <p className="text-[11px] text-ink-muted">
            {STATE_LABEL[state]} · started {formatRelative(job.startedAt)}
          </p>
          {detail && (
            <p className={cx('mt-0.5 text-[11px]', state === 'failed' ? 'text-danger' : 'text-ink-muted')}>
              {detail}
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={onDismiss}
          aria-label={`Dismiss ${job.label}`}
          className="shrink-0 rounded px-1 text-ink-muted hover:text-ink"
        >
          ×
        </button>
      </div>

      {progress !== undefined && state !== 'succeeded' && state !== 'failed' && (
        <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-line">
          <div
            className="h-full rounded-full bg-brand transition-[width] duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
      )}
    </li>
  );
}

const STATE_LABEL: Record<JobState, string> = {
  queued: 'Queued',
  running: 'Running',
  succeeded: 'Done',
  failed: 'Failed',
  cancelled: 'Cancelled',
};

const STATE_COLOR: Record<JobState, string> = {
  queued: 'bg-ink-muted',
  running: 'bg-brand',
  succeeded: 'bg-ok',
  failed: 'bg-danger',
  cancelled: 'bg-ink-muted',
};

export function StateDot({ state, className }: { state: JobState; className?: string }) {
  return (
    <span
      aria-hidden
      className={cx(
        'size-2 shrink-0 rounded-full',
        STATE_COLOR[state],
        state === 'running' && 'animate-pulse',
        className,
      )}
    />
  );
}
