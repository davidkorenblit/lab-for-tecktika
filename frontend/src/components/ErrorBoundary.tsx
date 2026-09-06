import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

/**
 * Last line of defence around the chat.
 *
 * A malformed citation or an unexpected message shape used to unmount the whole
 * tree and leave a white page. Background jobs live in localStorage and keep
 * running server-side either way, so the recovery path can say so honestly and
 * offer a reload that picks them back up.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('[ui] render failed', error, info.componentStack);
  }

  private reset = () => this.setState({ error: null });

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    return (
      <div className="flex h-full items-center justify-center bg-surface p-6">
        <div className="w-full max-w-md rounded-2xl border border-danger/30 bg-surface-raised p-6">
          <h1 className="text-base font-semibold text-danger">Something broke in the chat view</h1>
          <p className="mt-2 text-sm text-ink-muted">
            Any background jobs are still running on the server and will reappear once the page
            reloads.
          </p>
          <pre className="scroll-thin mt-3 max-h-32 overflow-auto rounded-lg bg-danger-soft px-3 py-2 text-xs text-danger">
            {error.message}
          </pre>
          <div className="mt-4 flex justify-end gap-2">
            <button
              type="button"
              onClick={this.reset}
              className="rounded-lg border border-line px-3.5 py-2 text-sm font-medium hover:bg-surface"
            >
              Try again
            </button>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="rounded-lg bg-brand px-3.5 py-2 text-sm font-medium text-white hover:opacity-90"
            >
              Reload
            </button>
          </div>
        </div>
      </div>
    );
  }
}
