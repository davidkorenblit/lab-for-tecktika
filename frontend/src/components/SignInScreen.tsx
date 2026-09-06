interface SignInScreenProps {
  error: Error | null;
  onSignIn: () => void;
}

export function SignInScreen({ error, onSignIn }: SignInScreenProps) {
  return (
    <div className="flex h-full items-center justify-center bg-surface p-6">
      <div className="w-full max-w-sm rounded-2xl border border-line bg-surface-raised p-6 text-center">
        <span
          aria-hidden
          className="mx-auto flex size-10 items-center justify-center rounded-xl bg-brand text-lg font-bold text-white"
        >
          A
        </span>
        <h1 className="mt-3 text-lg font-semibold">AI Agent Chat</h1>
        <p className="mt-1 text-sm text-ink-muted">
          Sign in with your work account to query the document library.
        </p>

        {error && (
          <p className="mt-3 rounded-lg bg-danger-soft px-3 py-2 text-xs text-danger">
            {error.message}
          </p>
        )}

        <button
          type="button"
          onClick={onSignIn}
          className="mt-4 block w-full rounded-xl bg-brand px-4 py-2.5 text-sm font-medium text-white hover:opacity-90"
        >
          Sign in with Microsoft
        </button>
      </div>
    </div>
  );
}
