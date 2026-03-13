import { useMemo } from "react";
import { Popover, PopoverTrigger, PopoverContent } from "../ui/popover";
import { ExternalLink } from "lucide-react";

/**
 * Renders text with inline citation markers [1], [2] as clickable popovers.
 * Citations array maps id → {url, snippet}.
 */
export default function CitationText({ text, citations = [] }) {
  const citationMap = useMemo(() => {
    const map = {};
    for (const c of citations) {
      map[c.id] = c;
    }
    return map;
  }, [citations]);

  if (!text) return null;

  // Split text on citation patterns like [1], [2], [1][2]
  const parts = text.split(/(\[\d+\])/g);

  return (
    <>
      {parts.map((part, i) => {
        const match = part.match(/^\[(\d+)\]$/);
        if (match) {
          const id = parseInt(match[1], 10);
          const citation = citationMap[id];
          if (citation) {
            return (
              <Popover key={i}>
                <PopoverTrigger asChild>
                  <button
                    className="inline-flex items-center justify-center min-w-[1.25rem] h-[1.1rem] px-1 text-[10px] font-semibold rounded bg-blue-500/15 text-blue-400 hover:bg-blue-500/25 transition-colors cursor-pointer align-super leading-none"
                  >
                    {id}
                  </button>
                </PopoverTrigger>
                <PopoverContent className="w-80 rounded-xl" align="start">
                  <div className="space-y-2">
                    <a
                      href={citation.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 underline underline-offset-2 break-all transition-colors"
                    >
                      <ExternalLink className="h-3 w-3 shrink-0" />
                      <span className="line-clamp-2">{citation.url}</span>
                    </a>
                    {citation.snippet && (
                      <p className="text-xs text-[hsl(var(--muted-foreground))] leading-relaxed">
                        {citation.snippet}
                      </p>
                    )}
                  </div>
                </PopoverContent>
              </Popover>
            );
          }
          // Citation not found in map — render as plain superscript
          return (
            <sup key={i} className="text-[10px] text-[hsl(var(--muted-foreground))]">
              [{id}]
            </sup>
          );
        }
        return <span key={i}>{part}</span>;
      })}
    </>
  );
}
