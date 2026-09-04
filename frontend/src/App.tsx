import { useAuth } from '@/hooks/useAuth';
import { AppHeader } from '@/components/AppHeader';
import { ChatWindow } from '@/components/ChatWindow';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { SignInScreen } from '@/components/SignInScreen';
import { AUTH_DEV_BYPASS } from '@/config';

export default function App() {
  const { principal, isAuthenticated, isLoading, error, loginUrl, logoutUrl } = useAuth();

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center bg-surface">
        <div className="flex items-center gap-3 text-sm text-ink-muted">
          <span className="size-4 animate-spin rounded-full border-2 border-line border-t-brand" />
          Checking your session…
        </div>
      </div>
    );
  }

  // Easy Auth already gates the route in production; this is the fallback for
  // a direct hit on the SPA before the auth cookie exists.
  if (!isAuthenticated && !AUTH_DEV_BYPASS) {
    return <SignInScreen error={error} loginUrl={loginUrl} />;
  }

  return (
    <div className="flex h-full flex-col bg-surface text-ink">
      <AppHeader principal={principal} logoutUrl={logoutUrl} />
      <ErrorBoundary>
        <ChatWindow />
      </ErrorBoundary>
    </div>
  );
}
