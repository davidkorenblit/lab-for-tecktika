import { QueryClient } from '@tanstack/react-query';
import { ApiError } from '@/services/apiClient';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: true,
      retry: (failureCount, error) => {
        // Auth failures are handled by the client (refresh + replay); retrying
        // here only delays the sign-in prompt.
        if (error instanceof ApiError && error.isUnauthorized) return false;
        if (error instanceof ApiError && error.status === 404) return false;
        return failureCount < 2;
      },
    },
    mutations: { retry: 0 },
  },
});

export const queryKeys = {
  session: ['auth', 'session'] as const,
  // Keyed on the client-minted threadId, never the server's conversationId —
  // the server id can arrive or change mid-stream, and moving the cache entry
  // underneath a running stream loses its messages.
  chatHistory: (threadId: string) => ['chat', 'history', threadId] as const,
  jobStatus: (jobId: string) => ['jobs', 'status', jobId] as const,
};
