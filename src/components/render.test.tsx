// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import { renderToString } from 'react-dom/server';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from '@/lib/queryClient';
import { JobsProvider } from '@/providers/JobsProvider';
import { ChatWindow } from './ChatWindow';
import { MessageBubble } from './MessageBubble';
import { ConfirmationDialog } from './ConfirmationDialog';
import type { ChatMessage, ConfirmationRequest } from '@/types';

/**
 * Renders the tree once to catch what a type-check cannot: a bad hook order, an
 * undefined component, a broken import. The assertions below are the behaviours
 * that would be embarrassing to get wrong — markdown actually rendering, every
 * file name appearing on a bulk delete, and an unbounded relevance score never
 * reaching the DOM as a percentage.
 */

const noop = () => {};

/** React's server renderer separates adjacent text nodes with <!-- -->. */
const flat = (html: string) => html.replace(/<!--\s*-->/g, '');

function render(node: React.ReactNode): string {
  return flat(
    renderToString(
      <QueryClientProvider client={queryClient}>
        <JobsProvider>{node}</JobsProvider>
      </QueryClientProvider>,
    ),
  );
}

const bulkDelete: ConfirmationRequest = {
  confirmationId: 'c1',
  action: 'delete',
  summary: 'Remove three files from the compliance library.',
  files: [{ name: 'Q3-report.pdf' }, { name: 'Q4-draft.pdf' }, { name: 'notes.pdf' }],
  destructive: true,
};

const assistant: ChatMessage = {
  id: 'm1',
  role: 'assistant',
  content:
    '## Findings\n\n- **Termination**: 30 days notice\n- Governing law: `NY`\n\n| Clause | Page |\n|---|---|\n| 4.2 | 11 |',
  createdAt: new Date().toISOString(),
  status: 'complete',
  citations: [
    { id: 'x', title: 'Vendor Agreement', fileName: 'vendor.pdf', page: 11, score: 12.4 },
    { id: 'y', title: 'Addendum', fileName: 'addendum.pdf', score: 6.2 },
  ],
};

const userTurn: ChatMessage = {
  id: 'm0',
  role: 'user',
  content: 'Replace the vendor agreement with this',
  createdAt: new Date().toISOString(),
  status: 'complete',
  attachments: [{ fileId: 'f1', fileName: 'vendor-2025.pdf', size: 52_428_800 }],
};

describe('ChatWindow', () => {
  const html = render(<ChatWindow />);

  it('renders', () => {
    expect(html.length).toBeGreaterThan(500);
  });

  it('offers attachment, not a separate upload dashboard', () => {
    expect(html).toContain('Ask about a document, or attach a PDF');
    expect(html).toContain('Attach a PDF');
  });

  it('exposes session history', () => {
    expect(html).toContain('Conversations');
  });
});

describe('MessageBubble', () => {
  const html = render(
    <>
      <MessageBubble message={userTurn} onConfirm={noop} onDecline={noop} />
      <MessageBubble message={assistant} onConfirm={noop} onDecline={noop} />
    </>,
  );

  it('renders assistant markdown rather than leaking the source', () => {
    expect(html).toContain('<h2>Findings</h2>');
    expect(html).toContain('<strong>Termination</strong>');
    expect(html).toContain('<table>');
    expect(html).not.toContain('## Findings');
  });

  it('shows attachments on the user turn', () => {
    expect(html).toContain('vendor-2025.pdf');
  });

  it('lists citation sources', () => {
    expect(html).toContain('vendor.pdf');
    expect(html).toContain('addendum.pdf');
  });

  it('never renders an unbounded search score as a percentage', () => {
    // score 12.4 must not become "1240%".
    expect(html).not.toMatch(/\b1240\b/);
  });
});

describe('ConfirmationDialog', () => {
  it('names every affected file and gates a bulk delete behind a typed name', () => {
    const html = render(
      <ConfirmationDialog confirmation={bulkDelete} onConfirm={noop} onCancel={noop} waiting={2} />,
    );
    for (const name of ['Q3-report.pdf', 'Q4-draft.pdf', 'notes.pdf']) {
      expect(html).toContain(name);
    }
    expect(html).toContain('Type the first file name');
    expect(html).toContain('2 more requests after this');
  });

  it('refuses an expired confirmation instead of offering it', () => {
    const expired = { ...bulkDelete, expiresAt: new Date(Date.now() - 60_000).toISOString() };
    const html = render(
      <ConfirmationDialog confirmation={expired} onConfirm={noop} onCancel={noop} />,
    );
    expect(html).toContain('expired before it was answered');
    expect(html).not.toContain('Type the first file name');
  });
});
