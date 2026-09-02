import { useCallback, useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { CONVERSATION_STORAGE_KEY } from '@/config';
import { queryKeys } from '@/lib/queryClient';
import { readJson, writeJson } from '@/lib/storage';
import { uid } from '@/lib/format';
import { fetchChatHistory, streamChatMessage } from '@/services/chat';
import { confirmAction } from '@/services/files';
import { useJobs } from '@/providers/JobsProvider';
import type { ChatHistoryResponse, ChatMessage, ConfirmationRequest, FileAction } from '@/types';

/**
 * Chat state.
 *
 * The React Query cache holds the canonical message list, so history loaded on
 * mount and tokens arriving over SSE end up in the same place. Token deltas are
 * buffered and flushed once per animation frame — a fast stream would otherwise
 * re-render the list on every few characters.
 */
export function useChat() {
  const queryClient = useQueryClient();
  const { trackJob } = useJobs();

  const [conversationId, setConversationId] = useState<string | undefined>(() =>
    readJson<string | undefined>(CONVERSATION_STORAGE_KEY, undefined),
  );
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamError, setStreamError] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);
  const bufferRef = useRef<{ messageId: string; text: string } | null>(null);
  const frameRef = useRef<number | null>(null);

  const queryKey = queryKeys.chatHistory(conversationId);

  const historyQuery = useQuery<ChatHistoryResponse>({
    queryKey,
    queryFn: async () => {
      const response = await fetchChatHistory(conversationId);
      // A fetch that resolves mid-stream (or a manual retry) must not drop
      // messages the client has added since it started.
      const cached = queryClient.getQueryData<ChatHistoryResponse>(queryKey)?.messages ?? [];
      const serverIds = new Set(response.messages.map((message) => message.id));
      const localOnly = cached.filter((message) => !serverIds.has(message.id));
      return { ...response, messages: [...response.messages, ...localOnly] };
    },
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });

  useEffect(() => {
    const serverConversationId = historyQuery.data?.conversationId;
    if (serverConversationId && serverConversationId !== conversationId) {
      setConversationId(serverConversationId);
      writeJson(CONVERSATION_STORAGE_KEY, serverConversationId);
    }
  }, [historyQuery.data?.conversationId, conversationId]);

  const patchMessages = useCallback(
    (updater: (messages: ChatMessage[]) => ChatMessage[]) => {
      queryClient.setQueryData<ChatHistoryResponse>(queryKey, (previous) => ({
        conversationId: previous?.conversationId,
        messages: updater(previous?.messages ?? []),
      }));
    },
    [queryClient, queryKey],
  );

  const updateMessage = useCallback(
    (id: string, patch: Partial<ChatMessage> | ((message: ChatMessage) => Partial<ChatMessage>)) => {
      patchMessages((messages) =>
        messages.map((message) =>
          message.id === id
            ? { ...message, ...(typeof patch === 'function' ? patch(message) : patch) }
            : message,
        ),
      );
    },
    [patchMessages],
  );

  const flushBuffer = useCallback(() => {
    frameRef.current = null;
    const buffered = bufferRef.current;
    if (!buffered || !buffered.text) return;
    bufferRef.current = { messageId: buffered.messageId, text: '' };
    updateMessage(buffered.messageId, (message) => ({ content: message.content + buffered.text }));
  }, [updateMessage]);

  const scheduleFlush = useCallback(() => {
    if (frameRef.current !== null) return;
    frameRef.current = requestAnimationFrame(flushBuffer);
  }, [flushBuffer]);

  useEffect(
    () => () => {
      if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
      abortRef.current?.abort();
    },
    [],
  );

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || isStreaming) return;

      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      const now = new Date().toISOString();
      const userMessage: ChatMessage = {
        id: uid('user'),
        role: 'user',
        content: trimmed,
        createdAt: now,
        status: 'complete',
      };
      const assistantId = uid('assistant');
      const assistantMessage: ChatMessage = {
        id: assistantId,
        role: 'assistant',
        content: '',
        createdAt: now,
        status: 'streaming',
      };

      bufferRef.current = { messageId: assistantId, text: '' };
      patchMessages((messages) => [...messages, userMessage, assistantMessage]);
      setIsStreaming(true);
      setStreamError(null);

      try {
        await streamChatMessage({
          message: trimmed,
          conversationId,
          signal: controller.signal,
          onEvent: (event) => {
            switch (event.type) {
              case 'delta':
                if (bufferRef.current) bufferRef.current.text += event.text;
                scheduleFlush();
                break;

              case 'citations':
                flushBuffer();
                updateMessage(assistantId, (message) => ({
                  citations: [...(message.citations ?? []), ...event.citations],
                }));
                break;

              case 'confirmation':
                flushBuffer();
                updateMessage(assistantId, { confirmation: event.confirmation });
                break;

              case 'job': {
                flushBuffer();
                // Persisted immediately: the job outlives this page load.
                trackJob({
                  jobId: event.jobId,
                  action: event.action,
                  label: event.label ?? describeJob(event.action, event.fileName),
                  fileName: event.fileName,
                });
                updateMessage(assistantId, (message) => ({
                  jobIds: [...(message.jobIds ?? []), event.jobId],
                }));
                break;
              }

              case 'error':
                flushBuffer();
                setStreamError(event.message);
                updateMessage(assistantId, { status: 'error', error: event.message });
                break;

              case 'done':
                flushBuffer();
                if (event.messageId) updateMessage(assistantId, { id: event.messageId });
                break;

              default:
                break;
            }
          },
        });
      } catch (error) {
        const message = error instanceof Error ? error.message : 'The assistant stopped responding';
        setStreamError(message);
        updateMessage(assistantId, { status: 'error', error: message });
      } finally {
        flushBuffer();
        updateMessage(assistantId, (message) =>
          message.status === 'streaming' ? { status: 'complete' } : {},
        );
        setIsStreaming(false);
        abortRef.current = null;
      }
    },
    [conversationId, flushBuffer, isStreaming, patchMessages, scheduleFlush, trackJob, updateMessage],
  );

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    flushBuffer();
    setIsStreaming(false);
  }, [flushBuffer]);

  /**
   * Answers a confirmation the agent asked for. On approval the backend returns
   * a jobId, which goes straight into the persisted job registry.
   */
  const respondToConfirmation = useCallback(
    async (messageId: string, confirmation: ConfirmationRequest, decision: 'confirmed' | 'declined') => {
      const response = await confirmAction({
        confirmationId: confirmation.confirmationId,
        confirmed: decision === 'confirmed',
        action: confirmation.action,
        files: confirmation.files.map((file) => file.name),
      });

      if (decision === 'confirmed' && response.jobId) {
        trackJob({
          jobId: response.jobId,
          action: confirmation.action,
          label: describeJob(confirmation.action, confirmation.files[0]?.name),
          fileName: confirmation.files[0]?.name,
        });
      }

      updateMessage(messageId, {
        confirmationResolution: {
          decision,
          at: new Date().toISOString(),
          jobId: response.jobId,
        },
      });

      return response;
    },
    [trackJob, updateMessage],
  );

  const startNewConversation = useCallback(() => {
    stopStreaming();
    setConversationId(undefined);
    writeJson(CONVERSATION_STORAGE_KEY, undefined);
    queryClient.removeQueries({ queryKey: queryKeys.chatHistory(undefined) });
    void queryClient.invalidateQueries({ queryKey: ['chat', 'history'] });
  }, [queryClient, stopStreaming]);

  return {
    messages: historyQuery.data?.messages ?? [],
    conversationId,
    isLoadingHistory: historyQuery.isPending,
    historyError: historyQuery.error as Error | null,
    refetchHistory: historyQuery.refetch,
    isStreaming,
    streamError,
    sendMessage,
    stopStreaming,
    respondToConfirmation,
    startNewConversation,
  };
}

export function describeJob(action: FileAction, fileName?: string): string {
  const verbs: Record<FileAction, string> = {
    upload: 'Uploading',
    replace: 'Replacing',
    update: 'Updating',
    delete: 'Deleting',
    move: 'Moving',
    unknown: 'Processing',
  };
  return `${verbs[action] ?? 'Processing'} ${fileName ?? 'file'}`;
}
