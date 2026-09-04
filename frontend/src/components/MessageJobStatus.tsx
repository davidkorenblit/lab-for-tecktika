import { useJob } from '@/providers/JobsProvider';
import { cx } from '@/lib/format';
import { StateDot } from './JobTray';

/**
 * Live status of a job started by this message. Reads from the same polled
 * registry as the tray, so the chat transcript and the tray never disagree.
 */
export function MessageJobStatus({ jobId }: { jobId: string }) {
  const entry = useJob(jobId);
  if (!entry?.status) return null;

  const { status, tracked } = entry;
  const label = tracked?.label ?? status.fileName ?? 'Background job';
  const isDone = status.state === 'succeeded';
  const isFailed = status.state === 'failed';

  return (
    <div
      className={cx(
        'flex w-full max-w-[85%] items-center gap-2 rounded-lg border px-3 py-2 text-xs',
        isFailed ? 'border-danger/40 bg-danger-soft' : 'border-line bg-surface-raised',
      )}
    >
      <StateDot state={status.state} />
      <span className="min-w-0 flex-1 truncate">
        <span className="font-medium">{label}</span>
        {status.message && <span className="text-ink-muted"> — {status.message}</span>}
        {isFailed && status.error && <span className="text-danger"> — {status.error}</span>}
      </span>

      {status.progress !== undefined && !isDone && !isFailed && (
        <span className="shrink-0 tabular-nums text-ink-muted">{status.progress}%</span>
      )}
      {isDone && <span className="shrink-0 font-medium text-ok">Done</span>}
    </div>
  );
}
