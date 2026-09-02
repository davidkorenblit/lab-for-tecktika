import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { MessageBubble } from './MessageBubble';
import type { ChatMessage, ConfirmationRequest } from '@/types';

interface MessageListProps {
  messages: ChatMessage[];
  isLoading: boolean;
  isStreaming: boolean;
  error: Error | null;
  onRetry: () => void;
  onConfirm: (messageId: string, confirmation: ConfirmationRequest) => void;
  onDecline: (messageId: string, confirmation: ConfirmationRequest) => void;
}

export function MessageList({
  messages,
  isLoading,
  isStreaming,
  error,
  onRetry,
  onConfirm,
  onDecline,
}: MessageListProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [pinnedToBottom, setPinnedToBottom] = useState(true);

  // Follow the stream only while the user is already at the bottom; scrolling
  // up to read an earlier answer should not get yanked back down.
  useLayoutEffect(() => {
    if (!pinnedToBottom) return;
    const element = scrollRef.current;
    if (!element) return;
    element.scrollTop = element.scrollHeight;
  }, [messages, pinnedToBottom]);

  useEffect(() => {
    const element = scrollRef.current;
    if (!element) return;
    const onScroll = () => {
      const distance = element.scrollHeight - element.scrollTop - element.clientHeight;
      setPinnedToBottom(distance < 80);
    };
    element.addEventListener('scroll', onScroll, { passive: true });
    return () => element.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <div ref={scrollRef} className="scroll-thin min-h-0 flex-1 overflow-y-auto">
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-5 px-4 py-6">
        {isLoading && <HistorySkeleton />}

        {error && (
          <div className="rounded-xl border border-danger/30 bg-danger-soft px-4 py-3 text-sm">
            <p className="font-medium text-danger">Could not load your previous messages.</p>
            <p className="mt-1 text-ink-muted">{error.message}</p>
            <button
              type="button"
              onClick={onRetry}
              className="mt-2 rounded-md border border-line bg-surface-raised px-3 py-1.5 text-xs font-medium hover:bg-brand-soft"
            >
              Try again
            </button>
          </div>
        )}

        {!isLoading && !error && messages.length === 0 && <EmptyState />}

        {messages.map((message) => (
          <MessageBubble
            key={message.id}
            message={message}
            onConfirm={onConfirm}
            onDecline={onDecline}
          />
        ))}

        {isStreaming && messages.at(-1)?.content === '' && <TypingIndicator />}
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex items-center gap-1.5 px-1 text-ink-muted" aria-label="Assistant is typing">
      {[0, 1, 2].map((index) => (
        <span
          key={index}
          className="typing-dot size-1.5 rounded-full bg-current"
          style={{ animationDelay: `${index * 0.15}s` }}
        />
      ))}
    </div>
  );
}

function HistorySkeleton() {
  return (
    <div className="flex flex-col gap-4" aria-hidden>
      {[0, 1, 2].map((index) => (
        <div
          key={index}
          className={index % 2 === 0 ? 'self-end w-2/5' : 'self-start w-3/5'}
        >
          <div className="h-16 animate-pulse rounded-2xl bg-line/60" />
        </div>
      ))}
    </div>
  );
}

function EmptyState() {
  const examples = [
    'What does the 2024 vendor agreement say about termination?',
    'Upload the new safety policy and index it',
    'Delete Q3-draft.pdf from the compliance library',
  ];

  return (
    <div className="mt-10 text-center">
      <h2 className="text-lg font-semibold">Ask about your documents</h2>
      <p className="mx-auto mt-1 max-w-md text-sm text-ink-muted">
        Search the SharePoint PDF library, or ask for a file to be uploaded, replaced, or removed.
        Anything destructive comes back for your confirmation first.
      </p>
      <ul className="mx-auto mt-5 flex max-w-md flex-col gap-2 text-left">
        {examples.map((example) => (
          <li
            key={example}
            className="rounded-lg border border-line bg-surface-raised px-3 py-2 text-sm text-ink-muted"
          >
            {example}
          </li>
        ))}
      </ul>
    </div>
  );
}
