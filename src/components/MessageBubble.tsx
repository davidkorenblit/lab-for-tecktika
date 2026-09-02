import { cx, formatBytes, formatTime } from '@/lib/format';
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

      {message.attachments && message.attachments.length > 0 && (
        <ul className={cx('flex max-w-[85%] flex-wrap gap-1.5', isUser && 'justify-end')}>
          {message.attachments.map((attachment) => (
            <li
              key={attachment.fileId ?? attachment.fileName}
              className="flex items-center gap-1.5 rounded-lg border border-line bg-surface-raised px-2 py-1 text-xs"
            >
              <span aria-hidden>📄</span>
              <span className="max-w-56 truncate font-medium" title={attachment.fileName}>
                {attachment.fileName}
              </span>
              {attachment.size !== undefined && (
                <span className="text-[10px] text-ink-muted">{formatBytes(attachment.size)}</span>
              )}
            </li>
          ))}
        </ul>
      )}

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
