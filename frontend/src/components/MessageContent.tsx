import { memo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

/**
 * Assistant replies are markdown.
 *
 * They used to be rendered as preformatted text, so a RAG answer arrived as
 * literal `**bold**`, `-` bullets and pipe-delimited tables.
 *
 * Raw HTML stays off — `rehype-raw` is deliberately not installed, so markup in
 * a retrieved document is text, not markup, and the allowlist below is a second
 * line of defence. Memoised on `content`: without it every frame of a stream
 * re-parses every message in the transcript rather than just the one growing.
 */

/** Everything GFM can produce, and nothing else. */
const ALLOWED = [
  'p', 'br', 'strong', 'em', 'del', 'a', 'code', 'pre', 'blockquote',
  'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
  'hr', 'table', 'thead', 'tbody', 'tr', 'th', 'td',
];

export const MessageContent = memo(function MessageContent({ content }: { content: string }) {
  return (
    <div className="markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        allowedElements={ALLOWED}
        unwrapDisallowed
        components={{
          a: ({ children, href }) => (
            <a href={href} target="_blank" rel="noreferrer noopener">
              {children}
            </a>
          ),
          // Wide tables scroll inside the bubble rather than stretching it.
          table: ({ children }) => (
            <div className="markdown-table-scroll">
              <table>{children}</table>
            </div>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
});
