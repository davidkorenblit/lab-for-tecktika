import { cx, formatRelative } from '@/lib/format';
import type { ThreadRecord } from '@/lib/threads';

interface ConversationSidebarProps {
  threads: ThreadRecord[];
  activeThreadId: string;
  isOpen: boolean;
  onToggle: () => void;
  onSelectThread: (threadId: string) => void;
  onDeleteThread: (threadId: string) => void;
  onNewConversation: () => void;
}

export function ConversationSidebar({
  threads,
  activeThreadId,
  isOpen,
  onToggle,
  onSelectThread,
  onDeleteThread,
  onNewConversation,
}: ConversationSidebarProps) {
  const ordered = [...threads].sort((a, b) => b.lastActiveAt - a.lastActiveAt);

  return (
    <>
      {/* Mobile Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/40 backdrop-blur-xs md:hidden"
          onClick={onToggle}
          aria-hidden="true"
        />
      )}

      {/* Sidebar Container */}
      <aside
        aria-label="Conversation History"
        className={cx(
          'fixed inset-y-0 left-0 z-40 flex w-72 flex-col border-r border-line bg-surface-raised transition-transform duration-200 ease-in-out md:static md:z-auto md:translate-x-0',
          isOpen ? 'translate-x-0' : '-translate-x-full md:hidden',
        )}
      >
        {/* Sidebar Header */}
        <div className="flex h-14 items-center justify-between border-b border-line px-4">
          <div className="flex items-center gap-2">
            <span aria-hidden className="text-base">💬</span>
            <h2 className="text-sm font-semibold text-ink">Conversations</h2>
            <span className="rounded-full bg-line px-2 py-0.5 text-[11px] font-medium text-ink-muted">
              {threads.length}
            </span>
          </div>
          <button
            type="button"
            onClick={onToggle}
            title="Close sidebar"
            aria-label="Close conversation history sidebar"
            className="rounded-lg p-1.5 text-ink-muted hover:bg-surface hover:text-ink md:hidden"
          >
            ✕
          </button>
        </div>

        {/* New Conversation Action */}
        <div className="p-3">
          <button
            type="button"
            onClick={() => {
              onNewConversation();
            }}
            className="flex w-full items-center justify-center gap-2 rounded-xl border border-brand/30 bg-brand-soft px-3 py-2.5 text-xs font-semibold text-brand transition hover:bg-brand hover:text-white"
          >
            <span aria-hidden className="text-sm font-bold leading-none">+</span>
            New conversation
          </button>
        </div>

        {/* Threads List */}
        <div className="scroll-thin flex-1 overflow-y-auto px-2 pb-3">
          {ordered.length === 0 ? (
            <p className="px-3 py-6 text-center text-xs text-ink-muted">No conversations yet</p>
          ) : (
            <ul className="flex flex-col gap-1">
              {ordered.map((thread) => {
                const isActive = thread.threadId === activeThreadId;
                return (
                  <li key={thread.threadId} className="group relative">
                    <button
                      type="button"
                      onClick={() => onSelectThread(thread.threadId)}
                      aria-current={isActive}
                      className={cx(
                        'flex w-full flex-col rounded-xl px-3 py-2 text-left transition',
                        isActive
                          ? 'border border-brand/40 bg-brand-soft text-brand'
                          : 'hover:bg-surface text-ink',
                      )}
                    >
                      <span className="block truncate pr-6 text-xs font-medium">
                        {thread.title ?? 'New conversation'}
                      </span>
                      <span className="block text-[10px] text-ink-muted">
                        {thread.fresh && !thread.title
                          ? 'Not started yet'
                          : formatRelative(thread.lastActiveAt)}
                      </span>
                    </button>

                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onDeleteThread(thread.threadId);
                      }}
                      title="Delete conversation"
                      aria-label={`Delete ${thread.title ?? 'conversation'}`}
                      className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-xs text-ink-muted opacity-0 transition group-hover:opacity-100 hover:bg-danger-soft hover:text-danger focus:opacity-100"
                    >
                      🗑️
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-line p-3 text-[11px] text-ink-muted">
          Conversations are saved locally in your browser session.
        </div>
      </aside>
    </>
  );
}
