import { useJobs } from '@/providers/JobsProvider';
import type { ClientPrincipal } from '@/types';

interface AppHeaderProps {
  principal: ClientPrincipal | null;
  logoutUrl: (redirect?: string) => string;
}

export function AppHeader({ principal, logoutUrl }: AppHeaderProps) {
  const { activeJobs } = useJobs();
  const name = principal?.userDetails ?? 'Signed in';

  return (
    <header className="flex shrink-0 items-center gap-3 border-b border-line bg-surface-raised px-4 py-2.5">
      <div className="flex min-w-0 items-center gap-2">
        <span
          aria-hidden
          className="flex size-7 items-center justify-center rounded-lg bg-brand text-sm font-bold text-white"
        >
          A
        </span>
        <div className="min-w-0">
          <h1 className="truncate text-sm font-semibold leading-tight">AI Agent Chat</h1>
          <p className="truncate text-[11px] text-ink-muted">SharePoint PDF library</p>
        </div>
      </div>

      {activeJobs.length > 0 && (
        <span className="hidden items-center gap-1.5 rounded-full bg-brand-soft px-2.5 py-1 text-[11px] font-medium text-brand sm:flex">
          <span className="size-3 animate-spin rounded-full border-2 border-brand/30 border-t-brand" />
          {activeJobs.length} background {activeJobs.length === 1 ? 'job' : 'jobs'}
        </span>
      )}

      <div className="ml-auto flex min-w-0 items-center gap-3">
        <span className="hidden max-w-40 truncate text-xs text-ink-muted sm:block" title={name}>
          {name}
        </span>
        <a
          href={logoutUrl('/')}
          className="rounded-lg border border-line px-2.5 py-1.5 text-xs font-medium hover:bg-surface"
        >
          Sign out
        </a>
      </div>
    </header>
  );
}
