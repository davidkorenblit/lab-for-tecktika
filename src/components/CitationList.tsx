import { useMemo, useState } from 'react';
import { cx } from '@/lib/format';
import type { Citation } from '@/types';

/**
 * Sources behind an answer. Collapsed to numbered chips by default; expanding
 * one shows the snippet the retriever matched, so a claim can be checked
 * without leaving the chat.
 */
export function CitationList({ citations }: { citations: Citation[] }) {
  const [openId, setOpenId] = useState<string | null>(null);

  // Azure AI Search `@search.score` is a relevance score, not a probability —
  // it is unbounded, so treating it as a fraction rendered "1240% match".
  // Ranking each source against the best one in the set is a claim the number
  // can actually support.
  const bestScore = useMemo(() => {
    const scores = citations
      .map((citation) => citation.score)
      .filter((score): score is number => typeof score === 'number' && score > 0);
    return scores.length > 0 ? Math.max(...scores) : undefined;
  }, [citations]);

  return (
    <div className="max-w-[85%]">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-[11px] font-medium uppercase tracking-wide text-ink-muted">
          Sources
        </span>
        {citations.map((citation, index) => {
          const isOpen = openId === citation.id;
          return (
            <button
              key={citation.id}
              type="button"
              aria-expanded={isOpen}
              onClick={() => setOpenId(isOpen ? null : citation.id)}
              title={citation.title}
              className={cx(
                'flex max-w-56 items-center gap-1.5 rounded-full border px-2 py-1 text-xs transition-colors',
                isOpen
                  ? 'border-brand bg-brand-soft text-brand'
                  : 'border-line bg-surface-raised text-ink-muted hover:border-brand/50',
              )}
            >
              <span className="flex size-4 shrink-0 items-center justify-center rounded-full bg-brand/15 text-[10px] font-semibold text-brand">
                {index + 1}
              </span>
              <span className="truncate">{citation.fileName ?? citation.title}</span>
              {citation.page !== undefined && (
                <span className="shrink-0 text-[10px] opacity-70">p.{citation.page}</span>
              )}
            </button>
          );
        })}
      </div>

      {openId && (
        <CitationDetail citation={citations.find((c) => c.id === openId)!} bestScore={bestScore} />
      )}
    </div>
  );
}

function CitationDetail({ citation, bestScore }: { citation: Citation; bestScore?: number }) {
  const relative =
    citation.score !== undefined && bestScore !== undefined && bestScore > 0
      ? Math.round((citation.score / bestScore) * 100)
      : undefined;

  return (
    <div className="mt-2 rounded-xl border border-line bg-surface-raised p-3 text-xs">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate font-medium text-ink">{citation.title}</p>
          {citation.fileName && citation.fileName !== citation.title && (
            <p className="truncate text-ink-muted">{citation.fileName}</p>
          )}
        </div>
        {relative !== undefined && (
          <span
            className="shrink-0 rounded bg-line/60 px-1.5 py-0.5 text-[10px] text-ink-muted"
            title={`Relevance ${citation.score} — ${relative}% of the top result in this answer`}
          >
            {relative}% of top
          </span>
        )}
      </div>

      {citation.snippet && (
        <blockquote className="mt-2 border-l-2 border-brand/40 pl-3 text-ink-muted italic">
          {citation.snippet}
        </blockquote>
      )}

      {citation.url && (
        <a
          href={citation.url}
          target="_blank"
          rel="noreferrer noopener"
          className="mt-2 inline-flex items-center gap-1 font-medium text-brand hover:underline"
        >
          Open in SharePoint
          <span aria-hidden>↗</span>
        </a>
      )}
    </div>
  );
}
