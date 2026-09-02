import { cx, formatTime } from '@/lib/format';
import { CitationList } from './CitationList';
import { ConfirmationCard } from './ConfirmationCard';
import { MessageJobStatus } from './MessageJobStatus';
import type { ChatMessage, ConfirmationRequest } from '@/types';

interface MessageBubbleProps {
  message: ChatMessage;
  onConfirm: (messageId: string, confirmation: ConfirmationRequest) => void;
  onDecline: (messageId: string, confirmation: ConfirmationRequest) => void;
}

export function MessageBubble({ message, onConfirm, onDecline }: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const isStreaming = message.status === 'streaming';

  return (
    <div className={cx('flex flex-col gap-2', isUser ? 'items-end' : 'items-start')}>
      <div
        className={cx(
          'max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap break-words',
          isUser
            ? 'bg-brand text-white rounded-br-sm'
            : 'border border-line bg-surface-raised rounded-bl-sm',
          message.status === 'error' && 'border-danger/40 bg-danger-soft',
        )}
      >
        {message.content}
        {isStreaming && <span className="stream-caret" aria-hidden />}
        {message.status === 'error' && message.error && (
          <p className="mt-2 text-xs text-danger">{message.error}</p>
        )}
      </div>

      {message.citations && message.citations.length > 0 && (
        <CitationList citations={message.citations} />
      )}

      {message.confirmation && (
        <ConfirmationCard
          confirmation={message.confirmation}
          resolution={message.confirmationResolution}
          onConfirm={() => onConfirm(message.id, message.confirmation!)}
          onDecline={() => onDecline(message.id, message.confirmation!)}
        />
      )}

      {message.jobIds?.map((jobId) => <MessageJobStatus key={jobId} jobId={jobId} />)}

      <time
        className={cx('px-1 text-[11px] text-ink-muted', isUser ? 'text-right' : 'text-left')}
        dateTime={message.createdAt}
      >
        {formatTime(message.createdAt)}
      </time>
    </div>
  );
}
