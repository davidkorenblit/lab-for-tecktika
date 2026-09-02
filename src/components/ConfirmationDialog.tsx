import { useEffect, useId, useRef, useState } from 'react';
import { cx, formatBytes } from '@/lib/format';
import type { ConfirmationRequest } from '@/types';

interface ConfirmationDialogProps {
  confirmation: ConfirmationRequest;
  onConfirm: () => void;
  onCancel: () => void;
  /** How many more confirmations are queued behind this one. */
  waiting?: number;
}

const ACTION_VERB: Record<ConfirmationRequest['action'], string> = {
  upload: 'upload',
  replace: 'replace',
  update: 'update',
  delete: 'permanently delete',
  move: 'move',
  unknown: 'change',
};

/**
 * Modal confirmation for destructive work.
 *
 * The prompt names every affected file, and every destructive action asks the
 * user to type a file name before the button unlocks — a mis-click cannot
 * destroy a document, and the typed name proves the user read which one it was.
 *
 * This used to apply only when exactly one file was involved, which had it
 * backwards: deleting five files was a single click while deleting one demanded
 * typing. Bulk operations are the dangerous case, so they are gated too — every
 * name is listed, and the name to type is the first in that list.
 */
export function ConfirmationDialog({
  confirmation,
  onConfirm,
  onCancel,
  waiting = 0,
}: ConfirmationDialogProps) {
  const { action, summary, files, destructive } = confirmation;
  const titleId = useId();
  const descriptionId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const [typed, setTyped] = useState('');

  const targetName = files[0]?.name ?? '';
  const requiresTypedName = destructive && targetName.length > 0;
  const canConfirm = !requiresTypedName || typed.trim() === targetName;

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onCancel();
      if (event.key !== 'Tab' || !dialogRef.current) return;

      // Keep focus inside the dialog while it is open.
      const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
        'button:not([disabled]), input, a[href]',
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [onCancel]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onCancel();
      }}
    >
      <div
        ref={dialogRef}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        className="w-full max-w-md rounded-2xl border border-line bg-surface-raised p-5 shadow-2xl"
      >
        <h2 id={titleId} className="text-base font-semibold">
          {files.length === 1 ? (
            <>
              {capitalize(ACTION_VERB[action])} <span className="break-all">{targetName}</span>?
            </>
          ) : (
            <>
              {capitalize(ACTION_VERB[action])} {files.length} files?
            </>
          )}
        </h2>

        <p id={descriptionId} className="mt-2 text-sm text-ink-muted">
          {summary}
        </p>

        <ul className="mt-3 flex max-h-48 flex-col gap-1 overflow-y-auto">
          {files.map((file) => (
            <li
              key={`${file.path ?? ''}/${file.name}`}
              className="flex items-baseline gap-2 rounded-lg border border-line bg-surface px-2.5 py-1.5 text-sm"
            >
              <span className="min-w-0 flex-1">
                <span className="font-semibold break-all">{file.name}</span>
                {file.path && (
                  <span className="block text-[11px] break-all text-ink-muted">{file.path}</span>
                )}
              </span>
              {file.size !== undefined && (
                <span className="shrink-0 text-[11px] text-ink-muted">{formatBytes(file.size)}</span>
              )}
            </li>
          ))}
        </ul>

        {destructive && (
          <p className="mt-3 rounded-lg bg-danger-soft px-3 py-2 text-xs text-danger">
            {action === 'delete'
              ? 'This removes the file from the SharePoint library and its index. It cannot be undone from here.'
              : 'The current version will be overwritten.'}
          </p>
        )}

        {requiresTypedName && (
          <label className="mt-3 block text-xs text-ink-muted">
            {files.length === 1 ? (
              <>
                Type <span className="font-semibold break-all text-ink">{targetName}</span> to confirm
              </>
            ) : (
              <>
                Type the first file name,{' '}
                <span className="font-semibold break-all text-ink">{targetName}</span>, to confirm all{' '}
                {files.length}
              </>
            )}
            <input
              autoFocus
              value={typed}
              onChange={(event) => setTyped(event.target.value)}
              spellCheck={false}
              autoComplete="off"
              className="mt-1 w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-brand"
              placeholder={targetName}
            />
          </label>
        )}

        <div className="mt-4 flex items-center justify-end gap-2">
          {waiting > 0 && (
            <span className="mr-auto text-[11px] text-ink-muted">
              {waiting} more {waiting === 1 ? 'request' : 'requests'} after this
            </span>
          )}
          <button
            type="button"
            onClick={onCancel}
            className="rounded-lg border border-line px-3.5 py-2 text-sm font-medium hover:bg-surface"
          >
            Cancel
          </button>
          <button
            type="button"
            autoFocus={!requiresTypedName}
            disabled={!canConfirm}
            onClick={onConfirm}
            className={cx(
              'rounded-lg px-3.5 py-2 text-sm font-medium text-white transition-opacity',
              destructive ? 'bg-danger' : 'bg-brand',
              canConfirm ? 'hover:opacity-90' : 'cursor-not-allowed opacity-40',
            )}
          >
            {capitalize(ACTION_VERB[action])}
            {files.length === 1 ? '' : ` ${files.length} files`}
          </button>
        </div>
      </div>
    </div>
  );
}

function capitalize(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}
