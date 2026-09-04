import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '@/lib/queryClient';
import { isAuthenticated, loadSession, loginUrl, logoutUrl } from '@/services/auth';
import type { AuthSession } from '@/types';

/**
 * Loads the Easy Auth session once on boot and keeps it fresh. Every API call
 * reads the token through the service layer, so this hook exists for the UI
 * (who is signed in, sign-in / sign-out links) rather than for request wiring.
 */
export function useAuth() {
  const query = useQuery<AuthSession>({
    queryKey: queryKeys.session,
    queryFn: () => loadSession(true),
    staleTime: 5 * 60_000,
    retry: 1,
  });

  return {
    session: query.data ?? null,
    principal: query.data?.principal ?? null,
    isAuthenticated: isAuthenticated(query.data),
    isLoading: query.isPending,
    error: query.error as Error | null,
    refetch: query.refetch,
    loginUrl,
    logoutUrl,
  };
}
