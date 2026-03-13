import ReactMarkdown from "react-markdown";
import CitationText from "./CitationText";

/**
 * Renders markdown content with proper styling for report sections.
 * Also handles inline citations [1][2] within text nodes.
 */
export default function MarkdownProse({ content, citations = [] }) {
  if (!content) return null;

  return (
    <div className="text-sm text-[hsl(var(--muted-foreground))] leading-relaxed">
      <ReactMarkdown
        components={{
          h3: ({ children }) => (
            <h3 className="text-sm font-semibold text-[hsl(var(--foreground))] mt-4 mb-2">
              {children}
            </h3>
          ),
          h4: ({ children }) => (
            <h4 className="text-sm font-medium text-[hsl(var(--foreground))] mt-3 mb-1.5">
              {children}
            </h4>
          ),
          p: ({ children }) => (
            <p className="mb-3 leading-relaxed">
              {renderWithCitations(children, citations)}
            </p>
          ),
          ul: ({ children }) => (
            <ul className="list-disc pl-5 mb-3 space-y-1">
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal pl-5 mb-3 space-y-1">
              {children}
            </ol>
          ),
          li: ({ children }) => (
            <li className="leading-relaxed">
              {renderWithCitations(children, citations)}
            </li>
          ),
          strong: ({ children }) => (
            <strong className="font-semibold text-[hsl(var(--foreground))]">
              {children}
            </strong>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

function renderWithCitations(children, citations) {
  if (!citations.length) return children;
  return Array.isArray(children)
    ? children.map((child, i) =>
        typeof child === "string" ? (
          <CitationText key={i} text={child} citations={citations} />
        ) : (
          child
        )
      )
    : typeof children === "string"
    ? <CitationText text={children} citations={citations} />
    : children;
}
