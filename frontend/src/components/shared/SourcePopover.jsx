import { Popover, PopoverTrigger, PopoverContent } from "../ui/popover";
import { ExternalLink } from "lucide-react";

/**
 * Popover that displays source URLs and optional snippets.
 * Triggered by clicking its children (typically a ConfidenceBadge).
 *
 * Props:
 *  - sources: Array of { url: string, snippet?: string }
 *  - children: trigger element
 */
export default function SourcePopover({ sources = [], children }) {
  if (!sources || sources.length === 0) {
    return children;
  }

  return (
    <Popover>
      <PopoverTrigger asChild>{children}</PopoverTrigger>
      <PopoverContent className="w-80 max-h-72 overflow-y-auto" align="end">
        <div className="space-y-3">
          <h4 className="text-sm font-semibold text-[hsl(var(--foreground))]">
            Sources ({sources.length})
          </h4>
          <ul className="space-y-2">
            {sources.map((src, i) => (
              <li key={i} className="text-xs space-y-1">
                <a
                  href={src.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1.5 text-blue-400 hover:text-blue-300 underline underline-offset-2 break-all"
                >
                  <ExternalLink className="h-3 w-3 shrink-0" />
                  <span className="line-clamp-1">{src.url}</span>
                </a>
                {src.snippet && (
                  <p className="text-[hsl(var(--muted-foreground))] leading-relaxed pl-4.5">
                    {src.snippet}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </div>
      </PopoverContent>
    </Popover>
  );
}
