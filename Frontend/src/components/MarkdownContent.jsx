import ReactMarkdown from "react-markdown";

const CITE_PREFIX = "#cite-";

// "[S1]" in the text → a markdown link "[S1](#cite-S1)" that renders as a chip.
// Only tags that have a matching source are converted.
function linkCitations(content, sources) {
  if (!sources?.length) return content;
  const ids = new Set(sources.map((s) => s.id));
  return content.replace(/\[(S\d+)\](?!\()/g, (match, id) =>
    ids.has(id) ? `[${id}](${CITE_PREFIX}${id})` : match
  );
}

export default function MarkdownContent({ content, sources, onCite }) {
  const byId = Object.fromEntries((sources ?? []).map((s) => [s.id, s]));

  return (
    <ReactMarkdown
      components={{
        h1: ({ children }) => (
          <h1 className="text-lg font-bold underline mb-2 mt-4">{children}</h1>
        ),
        h2: ({ children }) => (
          <h2 className="text-base font-bold underline mb-2 mt-4">{children}</h2>
        ),
        h3: ({ children }) => (
          <h3 className="text-sm font-bold underline mb-1.5 mt-3">{children}</h3>
        ),
        strong: ({ children }) => (
          <strong className="font-semibold text-gray-900">{children}</strong>
        ),
        ul: ({ children }) => (
          <ul className="list-disc list-inside space-y-1 my-2 text-gray-700">{children}</ul>
        ),
        ol: ({ children }) => (
          <ol className="list-decimal list-inside space-y-1 my-2 text-gray-700">{children}</ol>
        ),
        li: ({ children }) => (
          <li className="text-sm leading-relaxed">{children}</li>
        ),
        p: ({ children }) => (
          <p className="text-sm leading-relaxed text-gray-700 mb-2">{children}</p>
        ),
        a: ({ href, children }) => {
          if (href?.startsWith(CITE_PREFIX)) {
            const source = byId[href.slice(CITE_PREFIX.length)];
            return (
              <button
                type="button"
                onClick={() => source && onCite?.(source)}
                title={source?.label}
                className="inline-flex items-center align-baseline mx-0.5 px-1.5 py-px rounded-md text-[11px]
                           font-semibold bg-indigo-50 text-indigo-600 border border-indigo-100
                           hover:bg-indigo-100 cursor-pointer"
              >
                {children}
              </button>
            );
          }
          return (
            <a href={href} target="_blank" rel="noopener noreferrer" className="text-indigo-600 underline">
              {children}
            </a>
          );
        },
      }}
    >
      {linkCitations(content, sources)}
    </ReactMarkdown>
  );
}
