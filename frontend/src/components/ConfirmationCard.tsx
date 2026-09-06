import { cx, formatBytes } from '@/lib/format';
import { useExpiry } from '@/hooks/useExpiry';
import type { ChatMessage, ConfirmationRequest } from '@/types';

interface ConfirmationCardProps {
  confirmation: ConfirmationRequest;
  resolution: ChatMessage['confirmationResolution'];
  onConfirm: () => void;
  onDecline: () => void;
}

const ACTION_LABEL: Record<ConfirmationRequest['action'], string> = {
  upload: 'Upload',
  replace: 'Replace',
  update: 'Update',
  delete: 'Delete',
  move: 'Move',
  unknown: 'Apply change',
};

/**
 * Inline confirmation attached to an agent turn. Nothing happens until the user
 * picks one of the two buttons, and the affected files are always listed by
 * name — never summarised as "this file" or a count.
 */
export function ConfirmationCard({
  confirmation,
  resolution,
  onConfirm,
  onDecline,
}: ConfirmationCardProps) {
  const { action, summary, files, destructive } = confirmation;
  const decided = Boolean(resolution);
  const expired = useExpiry(confirmation.expiresAt);

  return (
    <div
      className={cx(
        'w-full max-w-[85%] rounded-xl border p-3.5 text-sm',
        destructive ? 'border-danger/40 bg-danger-soft' : 'border-brand/40 bg-brand-soft',
        decided && 'opacity-75',
      )}
    >
      <div className="flex items-center gap-2">
        <span
          className={cx(
            'rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide',
            destructive ? 'bg-danger text-white' : 'bg-brand text-white',
          )}
        >
          {ACTION_LABEL[action]}
        </span>
        <span className="text-xs font-medium text-ink-muted">
          {destructive ? 'Needs your confirmation' : 'Confirm to continue'}
        </span>
      </div>

      <p className="mt-2 text-ink">{summary}</p>

      <ul className="mt-2.5 flex flex-col gap-1">
        {files.map((file) => (
          <li
            key={`${file.path ?? ''}/${file.name}`}
            className="flex items-baseline gap-2 rounded-lg border border-line/70 bg-surface-raised px-2.5 py-1.5"
          >
            <span aria-hidden className="text-ink-muted">
              📄
            </span>
            <span className="min-w-0 flex-1">
              {/* The file name is the point of this component: never truncated away. */}
              <span className="font-semibold break-all text-ink">{file.name}</span>
              {file.path && <span className="block text-[11px] break-all text-ink-muted">{file.path}</span>}
            </span>
            {file.size !== undefined && (
              <span className="shrink-0 text-[11px] text-ink-muted">{formatBytes(file.size)}</span>
            )}
          </li>
        ))}
      </ul>

      {decided ? (
        <p className="mt-3 text-xs font-medium text-ink-muted">
          {resolution!.decision === 'confirmed'
            ? `Confirmed${resolution!.jobId ? ' — running in the background' : ''}.`
            : 'Declined. Nothing was changed.'}
        </p>
      ) : expired ? (
        <p className="mt-3 text-xs font-medium text-ink-muted">
          This request expired before it was answered. Nothing was changed — ask again if you
          still want it.
        </p>
      ) : (
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={onConfirm}
            className={cx(
              'rounded-lg px-3 py-1.5 text-sm font-medium text-white transition-opacity hover:opacity-90',
              destructive ? 'bg-danger' : 'bg-brand',
            )}
          >
            {destructive
              ? `${ACTION_LABEL[action]} ${files.length === 1 ? files[0].name : `${files.length} files`}`
              : 'Confirm'}
          </button>
          <button
            type="button"
            onClick={onDecline}
            className="rounded-lg border border-line bg-surface-raised px-3 py-1.5 text-sm font-medium hover:bg-surface"
          >
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}
