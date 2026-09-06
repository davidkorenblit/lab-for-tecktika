import { useEffect, useRef, useState } from 'react';
import { cx, formatRelative } from '@/lib/format';
import type { ThreadRecord } from '@/lib/threads';

interface ConversationMenuProps {
  threads: ThreadRecord[];
  activeThreadId: string;
  onSelect: (threadId: string) => void;
  onDelete: (threadId: string) => void;
  onNew: () => void;
}

/**
 * Session history.
 *
 * Conversations are listed newest first, named after their opening message. The
 * list is held in localStorage rather than fetched, because the API has no
 * conversations endpoint yet — if one appears this becomes the rendering layer
 * for it and nothing else moves.
 */
export function ConversationMenu({
  threads,
  activeThreadId,
  onSelect,
  onDelete,
  onNew,
}: ConversationMenuProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  const ordered = [...threads].sort((a, b) => b.lastActiveAt - a.lastActiveAt);

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-haspopup="menu"
        className="hover:text-brand hover:underline"
      >
        Conversations ({threads.length})
      </button>

      {open && (
        <div
          role="menu"
          className="scroll-thin absolute bottom-full right-0 z-40 mb-2 max-h-80 w-72 overflow-y-auto rounded-xl border border-line bg-surface-raised p-1.5 text-left shadow-xl"
        >
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              onNew();
              setOpen(false);
            }}
            className="mb-1 flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-sm font-medium text-brand hover:bg-brand-soft"
          >
            <span aria-hidden>+</span> New conversation
          </button>

          <ul className="flex flex-col gap-0.5">
            {ordered.map((thread) => {
              const isActive = thread.threadId === activeThreadId;
              return (
                <li key={thread.threadId} className="group relative">
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      onSelect(thread.threadId);
                      setOpen(false);
                    }}
                    aria-current={isActive}
                    className={cx(
                      'w-full rounded-lg px-2.5 py-2 pr-8 text-left hover:bg-surface',
                      isActive && 'bg-brand-soft',
                    )}
                  >
                    <span
                      className={cx(
                        'block truncate text-sm',
                        isActive ? 'font-semibold text-brand' : 'text-ink',
                      )}
                    >
                      {thread.title ?? 'New conversation'}
                    </span>
                    <span className="block text-[11px] text-ink-muted">
                      {thread.fresh && !thread.title
                        ? 'Not started yet'
                        : formatRelative(thread.lastActiveAt)}
                    </span>
                  </button>

                  <button
                    type="button"
                    onClick={() => onDelete(thread.threadId)}
                    aria-label={`Remove ${thread.title ?? 'conversation'} from this list`}
                    title="Remove from this list"
                    className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded px-1.5 py-0.5 text-ink-muted opacity-0 transition-opacity group-hover:opacity-100 hover:text-danger focus:opacity-100"
                  >
                    ×
                  </button>
                </li>
              );
            })}
          </ul>

          <p className="mt-1.5 border-t border-line px-2.5 pb-0.5 pt-2 text-[11px] text-ink-muted">
            Kept in this browser. Removing one here does not delete it on the server.
          </p>
        </div>
      )}
    </div>
  );
}
