import { useRef, useState, type ChangeEvent, type KeyboardEvent } from 'react';
import { cx, formatBytes } from '@/lib/format';

interface ComposerProps {
  isStreaming: boolean;
  onSend: (text: string) => void;
  onStop: () => void;
  onSelectFile: (file: File) => void;
  onNewConversation: () => void;
}

const MAX_FILE_BYTES = 500 * 1024 * 1024;

export function Composer({
  isStreaming,
  onSend,
  onStop,
  onSelectFile,
  onNewConversation,
}: ComposerProps) {
  const [value, setValue] = useState('');
  const [dragging, setDragging] = useState(false);
  const [fileError, setFileError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const submit = () => {
    const text = value.trim();
    if (!text || isStreaming) return;
    onSend(text);
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

  const acceptFile = (file: File | undefined) => {
    if (!file) return;
    if (file.type && file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
      setFileError('Only PDF files can be added to the library.');
      return;
    }
    if (file.size > MAX_FILE_BYTES) {
      setFileError(`${file.name} is ${formatBytes(file.size)} — larger than the ${formatBytes(MAX_FILE_BYTES)} limit.`);
      return;
    }
    setFileError(null);
    onSelectFile(file);
  };

  return (
    <div className="border-t border-line bg-surface-raised/80 backdrop-blur">
      <div className="mx-auto w-full max-w-3xl px-4 py-3">
        {fileError && <p className="mb-2 text-xs text-danger">{fileError}</p>}

        <div
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => {
            event.preventDefault();
            setDragging(false);
            acceptFile(event.dataTransfer.files?.[0]);
          }}
          className={cx(
            'flex items-end gap-2 rounded-2xl border bg-surface p-2 transition-colors',
            dragging ? 'border-brand bg-brand-soft' : 'border-line focus-within:border-brand/60',
          )}
        >
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            title="Upload a PDF"
            aria-label="Upload a PDF"
            className="flex size-9 shrink-0 items-center justify-center rounded-xl border border-line text-ink-muted hover:bg-brand-soft hover:text-brand"
          >
            <span aria-hidden className="text-lg leading-none">
              +
            </span>
          </button>

          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf,.pdf"
            className="hidden"
            onChange={(event) => {
              acceptFile(event.target.files?.[0]);
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
              dragging ? 'Drop the PDF to upload it' : 'Ask about a document, or drop a PDF here…'
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
              disabled={!value.trim()}
              className={cx(
                'h-9 shrink-0 rounded-xl px-4 text-sm font-medium text-white transition-opacity',
                value.trim() ? 'bg-brand hover:opacity-90' : 'cursor-not-allowed bg-brand/40',
              )}
            >
              Send
            </button>
          )}
        </div>

        <div className="mt-1.5 flex items-center justify-between px-1 text-[11px] text-ink-muted">
          <span>
            Enter to send · Shift+Enter for a new line
            {isStreaming && ' · uploads keep running while the agent replies'}
          </span>
          <button type="button" onClick={onNewConversation} className="hover:text-brand hover:underline">
            New conversation
          </button>
        </div>
      </div>
    </div>
  );
}
