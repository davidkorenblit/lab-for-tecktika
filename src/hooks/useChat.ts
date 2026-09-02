import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  STREAM_DRAFT_MAX_AGE_MS,
  STREAM_DRAFT_PERSIST_MS,
  STREAM_DRAFT_STORAGE_KEY,
} from '@/config';
import { queryKeys } from '@/lib/queryClient';
import { applyStoredResolutions, recordResolution } from '@/lib/confirmations';
import { readJson, removeKey, writeJson } from '@/lib/storage';
import { uid } from '@/lib/format';
import {
  findThread,
  loadThreadStore,
  newThread,
  patchThread,
  saveThreadStore,
  sortAndCap,
  titleFromMessage,
  type ThreadStore,
} from '@/lib/threads';
import { fetchChatHistory, streamChatMessage } from '@/services/chat';
import { confirmAction } from '@/services/files';
import { useJobs } from '@/providers/JobsProvider';
import type {
  ChatHistoryResponse,
  ChatMessage,
  ConfirmationRequest,
  FileAction,
  MessageAttachment,
} from '@/types';

/**
 * Chat state.
 *
 * Two identities, deliberately separate:
 *
 *   threadId       minted here, stable for the life of a conversation, and the
 *                  only thing the React Query key is built from.
 *   conversationId assigned by the backend, sent in request bodies.
 *
 * Keying the cache on the server id used to mean the key changed the moment the
 * id arrived — the cache entry the stream had been writing into was abandoned
 * mid-flight and its messages disappeared. The server id can now show up, change
 * or stay absent without moving the cache.
 *
 * The React Query cache holds the canonical message list, so history loaded on
 * mount and tokens arriving over SSE end up in the same place. Token deltas are
 * buffered and flushed once per animation frame — a fast stream would otherwise
 * re-render the list on every few characters.
 */

/** An assistant reply that was still streaming when the page went away. */
interface StreamDraft {
  threadId: string;
  messageId: string;
  content: string;
  createdAt: string;
  savedAt: number;
}

export function useChat() {
  const queryClient = useQueryClient();
  const { trackJob } = useJobs();

  const [store, setStore] = useState<ThreadStore>(loadThreadStore);
  const threadId = store.activeThreadId;
  const thread = findThread(store, threadId);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamError, setStreamError] = useState<string | null>(null);

  const commitStore = useCallback((update: (current: ThreadStore) => ThreadStore) => {
    setStore((current) => {
      const next = update(current);
      if (next === current) return current;
      const capped = { ...next, threads: sortAndCap(next.threads) };
      saveThreadStore(capped);
      return capped;
    });
  }, []);

  const abortRef = useRef<AbortController | null>(null);
  const bufferRef = useRef<{ messageId: string; text: string } | null>(null);
  const frameRef = useRef<number | null>(null);
  const draftRef = useRef<StreamDraft | null>(null);
  const draftWrittenAtRef = useRef(0);
  // Read inside the query function, which must not be re-created when the
  // server id changes — that would refetch and defeat the point of threadId.
  const conversationIdRef = useRef(thread?.conversationId);
  conversationIdRef.current = thread?.conversationId;

  const queryKey = useMemo(() => queryKeys.chatHistory(threadId), [threadId]);

  /* ------------------------------ thread identity ----------------------------- */

  const adoptConversationId = useCallback(
    (conversationId: string | undefined) => {
      if (!conversationId) return;
      commitStore((current) => {
        const active = findThread(current, current.activeThreadId);
        if (!active || active.conversationId === conversationId) return current;
        // Named by the server: it exists now, so history applies to it again.
        return patchThread(current, current.activeThreadId, {
          conversationId,
          fresh: undefined,
          lastActiveAt: Date.now(),
        });
      });
    },
    [commitStore],
  );

  /* --------------------------------- drafts ---------------------------------- */

  const persistDraft = useCallback((force = false) => {
    const draft = draftRef.current;
    if (!draft) return;
    const now = Date.now();
    if (!force && now - draftWrittenAtRef.current < STREAM_DRAFT_PERSIST_MS) return;
    draftWrittenAtRef.current = now;
    writeJson(STREAM_DRAFT_STORAGE_KEY, { ...draft, savedAt: now });
  }, []);

  const clearDraft = useCallback(() => {
    draftRef.current = null;
    draftWrittenAtRef.current = 0;
    removeKey(STREAM_DRAFT_STORAGE_KEY);
  }, []);

  /* --------------------------------- history --------------------------------- */

  const historyQuery = useQuery<ChatHistoryResponse>({
    queryKey,
    queryFn: async () => {
      const response = await fetchChatHistory(conversationIdRef.current);
      // A fetch that resolves mid-stream (or a manual retry) must not drop
      // messages the client has added since it started.
      const cached = queryClient.getQueryData<ChatHistoryResponse>(queryKey)?.messages ?? [];
      const serverIds = new Set(response.messages.map((message) => message.id));
      const localOnly = cached.filter((message) => !serverIds.has(message.id));

      // A reply cut off by a refresh: the server may never have stored it, so
      // splice the saved text back in rather than losing the answer.
      const draft = readJson<StreamDraft | null>(STREAM_DRAFT_STORAGE_KEY, null);
      const recovered: ChatMessage[] =
        draft &&
        draft.threadId === threadId &&
        draft.content &&
        Date.now() - draft.savedAt < STREAM_DRAFT_MAX_AGE_MS &&
        !serverIds.has(draft.messageId) &&
        !localOnly.some((message) => message.id === draft.messageId)
          ? [
              {
                id: draft.messageId,
                role: 'assistant',
                content: draft.content,
                createdAt: draft.createdAt,
                status: 'error',
                error: 'This reply was interrupted when the page reloaded.',
              },
            ]
          : [];

      return {
        ...response,
        // Decisions the user already made must not come back as open questions.
        messages: applyStoredResolutions([...response.messages, ...recovered, ...localOnly]),
      };
    },
    enabled: !thread?.fresh,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });

  useEffect(() => {
    adoptConversationId(historyQuery.data?.conversationId);
  }, [historyQuery.data?.conversationId, adoptConversationId]);

  /* -------------------------------- messages --------------------------------- */

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
    updateMessage(buffered.messageId, (message) => {
      const content = message.content + buffered.text;
      if (draftRef.current) draftRef.current.content = content;
      persistDraft();
      return { content };
    });
  }, [persistDraft, updateMessage]);

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
    async (text: string, attachments: MessageAttachment[] = []) => {
      const trimmed = text.trim();
      // An attachment on its own is a valid turn: "here, deal with this".
      if ((!trimmed && attachments.length === 0) || isStreaming) return;

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
        attachments: attachments.length > 0 ? attachments : undefined,
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
      draftRef.current = { threadId, messageId: assistantId, content: '', createdAt: now, savedAt: 0 };
      patchMessages((messages) => [...messages, userMessage, assistantMessage]);

      // Name the conversation after its opening line, the way a subject line works.
      commitStore((current) => {
        const active = findThread(current, threadId);
        if (!active) return current;
        return patchThread(current, threadId, {
          lastActiveAt: Date.now(),
          title: active.title ?? titleFromMessage(trimmed, attachments[0]?.fileName),
        });
      });
      setIsStreaming(true);
      setStreamError(null);

      try {
        await streamChatMessage({
          message: trimmed,
          conversationId: conversationIdRef.current,
          attachments,
          signal: controller.signal,
          onEvent: (event) => {
            switch (event.type) {
              case 'start':
                adoptConversationId(event.conversationId);
                break;

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
                adoptConversationId(event.conversationId);
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
        // The reply is in the cache and, on a clean finish, on the server too.
        clearDraft();
        setIsStreaming(false);
        abortRef.current = null;
      }
    },
    [
      adoptConversationId,
      clearDraft,
      commitStore,
      flushBuffer,
      isStreaming,
      patchMessages,
      scheduleFlush,
      threadId,
      trackJob,
      updateMessage,
    ],
  );

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    flushBuffer();
    clearDraft();
    setIsStreaming(false);
  }, [clearDraft, flushBuffer]);

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

      const resolution = {
        decision,
        at: new Date().toISOString(),
        jobId: response.jobId,
      } as const;
      // Persisted against the backend's confirmationId so a refresh does not
      // re-offer an action the user has already answered.
      recordResolution(confirmation.confirmationId, resolution);
      updateMessage(messageId, { confirmationResolution: resolution });

      return response;
    },
    [trackJob, updateMessage],
  );

  /**
   * Really starts a new thread. The old version cleared the server id and then
   * let the next history response put it straight back, so "New conversation"
   * returned you to the conversation you had just left. The previous thread is
   * kept in the list rather than discarded, so it can be reopened.
   */
  const startNewConversation = useCallback(() => {
    stopStreaming();
    clearDraft();
    const thread = newThread(true);
    conversationIdRef.current = undefined;
    commitStore((current) => ({
      activeThreadId: thread.threadId,
      threads: [...current.threads, thread],
    }));
  }, [clearDraft, commitStore, stopStreaming]);

  /** Reopens an earlier conversation. Its history is refetched on demand. */
  const switchThread = useCallback(
    (targetId: string) => {
      if (targetId === threadId) return;
      stopStreaming();
      commitStore((current) => {
        if (!findThread(current, targetId)) return current;
        conversationIdRef.current = findThread(current, targetId)?.conversationId;
        return {
          ...patchThread(current, targetId, { lastActiveAt: Date.now() }),
          activeThreadId: targetId,
        };
      });
    },
    [commitStore, stopStreaming, threadId],
  );

  const deleteThread = useCallback(
    (targetId: string) => {
      queryClient.removeQueries({ queryKey: queryKeys.chatHistory(targetId) });
      commitStore((current) => {
        const remaining = current.threads.filter((entry) => entry.threadId !== targetId);
        // Never end up with nothing to show.
        if (remaining.length === 0) {
          const replacement = newThread(true);
          conversationIdRef.current = undefined;
          return { activeThreadId: replacement.threadId, threads: [replacement] };
        }
        if (current.activeThreadId !== targetId) return { ...current, threads: remaining };
        const next = sortAndCap(remaining)[0];
        conversationIdRef.current = next.conversationId;
        return { activeThreadId: next.threadId, threads: remaining };
      });
    },
    [commitStore, queryClient],
  );

  return {
    messages: historyQuery.data?.messages ?? [],
    threadId,
    threads: store.threads,
    switchThread,
    deleteThread,
    conversationId: thread?.conversationId,
    // `isPending` stays true for a disabled query, which would pin the skeleton
    // on a new thread; `isLoading` is pending *and* actually in flight.
    isLoadingHistory: historyQuery.isLoading,
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
