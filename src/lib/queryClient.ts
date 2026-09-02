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
  chatHistory: (conversationId?: string) => ['chat', 'history', conversationId ?? 'default'] as const,
  jobStatus: (jobId: string) => ['jobs', 'status', jobId] as const,
};
