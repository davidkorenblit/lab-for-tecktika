import { useAuth } from '@/hooks/useAuth';
import { AppHeader } from '@/components/AppHeader';
import { ChatWindow } from '@/components/ChatWindow';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { SignInScreen } from '@/components/SignInScreen';
import { AUTH_DEV_BYPASS } from '@/config';

export default function App() {
  const { principal, isAuthenticated, isLoading, error, login, logout } = useAuth();

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

  // No account signed into MSAL yet — show the sign-in screen, which starts
  // the redirect flow on click.
  if (!isAuthenticated && !AUTH_DEV_BYPASS) {
    return <SignInScreen error={error} onSignIn={login} />;
  }

  return (
    <div className="flex h-full flex-col bg-surface text-ink">
      <AppHeader principal={principal} onSignOut={logout} />
      <ErrorBoundary>
        <ChatWindow />
      </ErrorBoundary>
    </div>
  );
}
