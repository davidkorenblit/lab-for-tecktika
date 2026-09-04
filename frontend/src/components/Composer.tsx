import { useRef, useState, type ChangeEvent, type KeyboardEvent } from 'react';
import { cx, formatBytes } from '@/lib/format';
import { ConversationMenu } from './ConversationMenu';
import type { ThreadRecord } from '@/lib/threads';
import type { PendingAttachment } from '@/types';

interface ComposerProps {
  isStreaming: boolean;
  attachments: PendingAttachment[];
  threads: ThreadRecord[];
  activeThreadId: string;
  onSend: (text: string) => void;
  onStop: () => void;
  onAttachFile: (file: File) => void;
  onRemoveAttachment: (id: string) => void;
  onSelectThread: (threadId: string) => void;
  onDeleteThread: (threadId: string) => void;
  onNewConversation: () => void;
}

const MAX_FILE_BYTES = 500 * 1024 * 1024;

/**
 * The one way into the agent.
 *
 * A file is an attachment on a message, not a separate upload action: the bytes
 * start moving to storage the moment it is picked, but nothing happens to the
 * library until the message is sent and the agent decides what the file is for.
 */
export function Composer({
  isStreaming,
  attachments,
  threads,
  activeThreadId,
  onSend,
  onStop,
  onAttachFile,
  onRemoveAttachment,
  onSelectThread,
  onDeleteThread,
  onNewConversation,
}: ComposerProps) {
  const [value, setValue] = useState('');
  const [fileError, setFileError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const staging = attachments.some(
    (item) => item.phase === 'requesting-url' || item.phase === 'uploading',
  );
  const readyCount = attachments.filter((item) => item.phase === 'ready').length;
  const canSend = Boolean(value.trim() || readyCount > 0) && !staging && !isStreaming;

  const submit = () => {
    if (!canSend) return;
    onSend(value.trim());
    setValue('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  };

  const autoGrow = (event: ChangeEvent<HTMLTextAreaElement>) => {
    setValue(event.target.value);
    const element = event.target;
    element.style.height = 'auto';
    element.style.height = `${Math.min(element.scrollHeight, 200)}px`;
  };

  const acceptFiles = (files: FileList | null) => {
    if (!files) return;
    for (const file of Array.from(files)) {
      if (file.type && file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
        setFileError('Only PDF files can be added to the library.');
        continue;
      }
      if (file.size > MAX_FILE_BYTES) {
        setFileError(
          `${file.name} is ${formatBytes(file.size)} — larger than the ${formatBytes(MAX_FILE_BYTES)} limit.`,
        );
        continue;
      }
      setFileError(null);
      onAttachFile(file);
    }
  };

  return (
    <div className="border-t border-line bg-surface-raised/80 backdrop-blur">
      <div className="mx-auto w-full max-w-3xl px-4 py-3">
        {fileError && <p className="mb-2 text-xs text-danger">{fileError}</p>}

        <div className="rounded-2xl border border-line bg-surface p-2 focus-within:border-brand/60">
          {attachments.length > 0 && (
            <ul className="mb-2 flex flex-wrap gap-1.5">
              {attachments.map((attachment) => (
                <AttachmentChip
                  key={attachment.id}
                  attachment={attachment}
                  onRemove={() => onRemoveAttachment(attachment.id)}
                />
              ))}
            </ul>
          )}

          <div className="flex items-end gap-2">
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              title="Attach a PDF"
              aria-label="Attach a PDF"
              className="flex size-9 shrink-0 items-center justify-center rounded-xl border border-line text-ink-muted hover:bg-brand-soft hover:text-brand"
            >
              <span aria-hidden className="text-base leading-none">
                📎
              </span>
            </button>

            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept="application/pdf,.pdf"
              className="hidden"
              onChange={(event) => {
                acceptFiles(event.target.files);
                // Reset so picking the same file twice still fires a change.
                event.target.value = '';
              }}
            />

            <textarea
              ref={textareaRef}
              rows={1}
              value={value}
              onChange={autoGrow}
              onKeyDown={onKeyDown}
              placeholder={
                attachments.length > 0
                  ? 'Say what to do with the attached file…'
                  : 'Ask about a document, or attach a PDF…'
              }
              aria-label="Message"
              className="max-h-50 flex-1 resize-none bg-transparent px-1 py-2 text-sm outline-none placeholder:text-ink-muted"
            />

            {isStreaming ? (
              <button
                type="button"
                onClick={onStop}
                className="h-9 shrink-0 rounded-xl border border-line px-3 text-sm font-medium hover:bg-surface-raised"
              >
                Stop
              </button>
            ) : (
              <button
                type="button"
                onClick={submit}
                disabled={!canSend}
                title={staging ? 'Waiting for the attachment to finish uploading' : undefined}
                className={cx(
                  'h-9 shrink-0 rounded-xl px-4 text-sm font-medium text-white transition-opacity',
                  canSend ? 'bg-brand hover:opacity-90' : 'cursor-not-allowed bg-brand/40',
                )}
              >
                Send
              </button>
            )}
          </div>
        </div>

        <div className="mt-1.5 flex items-center justify-between gap-3 px-1 text-[11px] text-ink-muted">
          <span className="min-w-0 truncate">
            Enter to send · Shift+Enter for a new line
            {staging && ' · waiting for the upload to finish'}
          </span>
          <ConversationMenu
            threads={threads}
            activeThreadId={activeThreadId}
            onSelect={onSelectThread}
            onDelete={onDeleteThread}
            onNew={onNewConversation}
          />
        </div>
      </div>
    </div>
  );
}

function AttachmentChip({
  attachment,
  onRemove,
}: {
  attachment: PendingAttachment;
  onRemove: () => void;
}) {
  const { fileName, size, phase, progress, error } = attachment;
  const failed = phase === 'error' || phase === 'cancelled';

  return (
    <li
      className={cx(
        'flex max-w-full items-center gap-2 rounded-lg border px-2 py-1 text-xs',
        failed ? 'border-danger/40 bg-danger-soft' : 'border-line bg-surface-raised',
      )}
    >
      <span aria-hidden>📄</span>
      <span className="min-w-0">
        <span className="block truncate font-medium" title={fileName}>
          {fileName}
        </span>
        <span className={cx('block text-[10px]', failed ? 'text-danger' : 'text-ink-muted')}>
          {phase === 'requesting-url' && 'Preparing…'}
          {phase === 'uploading' && `Uploading ${progress}%`}
          {phase === 'ready' && formatBytes(size)}
          {phase === 'cancelled' && 'Cancelled'}
          {phase === 'error' && (error ?? 'Upload failed')}
        </span>
      </span>

      {phase === 'uploading' && (
        <span className="h-1 w-10 shrink-0 overflow-hidden rounded-full bg-line">
          <span
            className="block h-full rounded-full bg-brand transition-[width] duration-200"
            style={{ width: `${progress}%` }}
          />
        </span>
      )}

      <button
        type="button"
        onClick={onRemove}
        aria-label={`Remove ${fileName}`}
        className="shrink-0 rounded px-1 text-ink-muted hover:text-ink"
      >
        ×
      </button>
    </li>
  );
}
