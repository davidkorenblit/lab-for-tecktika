import { cx, formatBytes } from '@/lib/format';
import type { UploadPhase, UploadTask } from '@/types';

interface UploadPanelProps {
  tasks: UploadTask[];
  onCancel: (taskId: string) => void;
  onDismiss: (taskId: string) => void;
}

const PHASE_LABEL: Record<UploadPhase, string> = {
  idle: 'Waiting',
  'requesting-url': 'Preparing upload…',
  'awaiting-confirmation': 'Waiting for your confirmation',
  uploading: 'Uploading to storage',
  finalizing: 'Handing off for indexing…',
  done: 'Uploaded — indexing runs in the background',
  error: 'Upload failed',
  cancelled: 'Cancelled',
};

/**
 * Browser-side upload progress. Once the bytes land the work moves to a
 * background job, so this panel is only about the transfer itself.
 */
export function UploadPanel({ tasks, onCancel, onDismiss }: UploadPanelProps) {
  const visible = tasks.filter((task) => task.phase !== 'awaiting-confirmation');
  if (visible.length === 0) return null;

  return (
    <div className="mx-auto w-full max-w-3xl px-4">
      <ul className="mb-2 flex flex-col gap-1.5">
        {visible.map((task) => {
          const isTerminal =
            task.phase === 'done' || task.phase === 'error' || task.phase === 'cancelled';
          return (
            <li
              key={task.id}
              className={cx(
                'rounded-xl border px-3 py-2 text-xs',
                task.phase === 'error'
                  ? 'border-danger/40 bg-danger-soft'
                  : 'border-line bg-surface-raised',
              )}
            >
              <div className="flex items-center gap-2">
                <span className="min-w-0 flex-1 truncate">
                  <span className="font-medium break-all">{task.fileName}</span>
                  <span className="text-ink-muted"> · {formatBytes(task.size)}</span>
                </span>
                <span className="shrink-0 text-ink-muted">
                  {task.phase === 'uploading' ? `${task.progress}%` : PHASE_LABEL[task.phase]}
                </span>
                <button
                  type="button"
                  onClick={() => (isTerminal ? onDismiss(task.id) : onCancel(task.id))}
                  className="shrink-0 rounded px-1 text-ink-muted hover:text-ink"
                  aria-label={isTerminal ? `Dismiss ${task.fileName}` : `Cancel upload of ${task.fileName}`}
                >
                  {isTerminal ? '×' : 'Cancel'}
                </button>
              </div>

              {task.phase === 'uploading' && (
                <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-line">
                  <div
                    className="h-full rounded-full bg-brand transition-[width] duration-200"
                    style={{ width: `${task.progress}%` }}
                  />
                </div>
              )}

              {task.error && <p className="mt-1 text-danger">{task.error}</p>}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
