import { useCallback, useRef, useState } from 'react';
import { useChat } from '@/hooks/useChat';
import { toMessageAttachments, useFileUpload } from '@/hooks/useFileUpload';
import { useConfirmationQueue } from '@/hooks/useConfirmationQueue';
import { MessageList } from './MessageList';
import { Composer } from './Composer';
import { JobTray } from './JobTray';
import { ConfirmationDialog } from './ConfirmationDialog';
import type { ConfirmationRequest } from '@/types';

/**
 * The chat surface.
 *
 * Everything slow — uploads, indexing, deletes — is handed to a background job
 * and tracked outside this component, so the composer stays live the whole time.
 */
export function ChatWindow() {
  const {
    messages,
    isLoadingHistory,
    historyError,
    refetchHistory,
    isStreaming,
    streamError,
    sendMessage,
    stopStreaming,
    respondToConfirmation,
    startNewConversation,
  } = useChat();

  const { attachments, attachFile, removeAttachment, clearAttachments } = useFileUpload();
  const queue = useConfirmationQueue();
  const [confirmError, setConfirmError] = useState<string | null>(null);
  const busyConfirmations = useRef(new Set<string>());

  const handleConfirmationDecision = useCallback(
    async (messageId: string, confirmation: ConfirmationRequest, decision: 'confirmed' | 'declined') => {
      if (busyConfirmations.current.has(confirmation.confirmationId)) return;
      busyConfirmations.current.add(confirmation.confirmationId);
      setConfirmError(null);
      try {
        await respondToConfirmation(messageId, confirmation, decision);
      } catch (error) {
        setConfirmError(error instanceof Error ? error.message : 'Could not send your confirmation');
      } finally {
        busyConfirmations.current.delete(confirmation.confirmationId);
      }
    },
    [respondToConfirmation],
  );

  const handleSend = useCallback(
    (text: string) => {
      const ready = toMessageAttachments(attachments);
      void sendMessage(text, ready);
      clearAttachments();
    },
    [attachments, clearAttachments, sendMessage],
  );

  return (
    <div className="relative flex min-h-0 flex-1 flex-col">
      <MessageList
        messages={messages}
        isLoading={isLoadingHistory}
        isStreaming={isStreaming}
        error={historyError}
        onRetry={() => void refetchHistory()}
        onConfirm={(messageId, confirmation) =>
          // Destructive actions get the modal; the rest resolve inline.
          confirmation.destructive
            ? queue.enqueue({ messageId, confirmation })
            : void handleConfirmationDecision(messageId, confirmation, 'confirmed')
        }
        onDecline={(messageId, confirmation) =>
          void handleConfirmationDecision(messageId, confirmation, 'declined')
        }
      />

      {(streamError || confirmError) && (
        <div className="mx-auto w-full max-w-3xl px-4">
          <p className="mb-2 rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-sm text-danger">
            {confirmError ?? streamError}
          </p>
        </div>
      )}

      <Composer
        isStreaming={isStreaming}
        attachments={attachments}
        onSend={handleSend}
        onStop={stopStreaming}
        onAttachFile={(file) => void attachFile(file)}
        onRemoveAttachment={removeAttachment}
        onNewConversation={startNewConversation}
      />

      <JobTray />

      {/* Exactly one confirmation is ever on screen; the rest wait their turn. */}
      {queue.current && (
        <ConfirmationDialog
          key={queue.current.confirmation.confirmationId}
          confirmation={queue.current.confirmation}
          waiting={queue.waiting}
          onConfirm={() => {
            const { messageId, confirmation } = queue.current!;
            queue.resolveCurrent();
            void handleConfirmationDecision(messageId, confirmation, 'confirmed');
          }}
          onCancel={queue.resolveCurrent}
        />
      )}
    </div>
  );
}
