import { useCallback, useMemo, useRef, useState } from 'react';
import { useChat } from '@/hooks/useChat';
import { useFileUpload } from '@/hooks/useFileUpload';
import { MessageList } from './MessageList';
import { Composer } from './Composer';
import { JobTray } from './JobTray';
import { UploadPanel } from './UploadPanel';
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

  const upload = useFileUpload();
  const [confirmError, setConfirmError] = useState<string | null>(null);
  const [pendingMessageConfirmation, setPendingMessageConfirmation] = useState<{
    messageId: string;
    confirmation: ConfirmationRequest;
  } | null>(null);
  const busyConfirmations = useRef(new Set<string>());

  // An upload that hit an existing file name is parked until the user answers.
  const overwriteTask = useMemo(
    () => upload.tasks.find((task) => task.phase === 'awaiting-confirmation' && task.confirmation),
    [upload.tasks],
  );

  const handleConfirmationDecision = useCallback(
    async (messageId: string, confirmation: ConfirmationRequest, decision: 'confirmed' | 'declined') => {
      if (busyConfirmations.current.has(confirmation.confirmationId)) return;
      busyConfirmations.current.add(confirmation.confirmationId);
      setConfirmError(null);
      try {
        await respondToConfirmation(messageId, confirmation, decision);
        setPendingMessageConfirmation(null);
      } catch (error) {
        setConfirmError(error instanceof Error ? error.message : 'Could not send your confirmation');
      } finally {
        busyConfirmations.current.delete(confirmation.confirmationId);
      }
    },
    [respondToConfirmation],
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
            ? setPendingMessageConfirmation({ messageId, confirmation })
            : void handleConfirmationDecision(messageId, confirmation, 'confirmed')
        }
        onDecline={(messageId, confirmation) =>
          void handleConfirmationDecision(messageId, confirmation, 'declined')
        }
      />

      <UploadPanel
        tasks={upload.tasks}
        onCancel={upload.cancelUpload}
        onDismiss={upload.dismissTask}
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
        onSend={(text) => void sendMessage(text)}
        onStop={stopStreaming}
        onSelectFile={(file) => void upload.startUpload(file)}
        onNewConversation={startNewConversation}
      />

      <JobTray />

      {/* Destructive confirmation from the agent. */}
      {pendingMessageConfirmation && (
        <ConfirmationDialog
          confirmation={pendingMessageConfirmation.confirmation}
          onConfirm={() =>
            void handleConfirmationDecision(
              pendingMessageConfirmation.messageId,
              pendingMessageConfirmation.confirmation,
              'confirmed',
            )
          }
          onCancel={() => setPendingMessageConfirmation(null)}
        />
      )}

      {/* Overwrite confirmation raised by the upload flow. */}
      {overwriteTask?.confirmation && (
        <ConfirmationDialog
          confirmation={overwriteTask.confirmation}
          onConfirm={() => void upload.confirmOverwrite(overwriteTask.id, overwriteTask.confirmation!)}
          onCancel={() => void upload.declineOverwrite(overwriteTask.id, overwriteTask.confirmation!)}
        />
      )}
    </div>
  );
}
