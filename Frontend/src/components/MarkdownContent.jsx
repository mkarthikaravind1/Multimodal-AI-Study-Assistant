import ReactMarkdown from "react-markdown";

export default function MarkdownContent({ content }) {
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
      }}
    >
      {content}
    </ReactMarkdown>
  );
}