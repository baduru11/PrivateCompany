import { X, Loader2, Sparkles, CornerDownRight } from "lucide-react";
import { cn } from "../../lib/utils";

export default function SuggestionPanel({
  suggestions = [],
  originalQuery = "",
  mode = "",
  onSelect,
  onDismiss,
  isLoading = false,
}) {
  if (isLoading) {
    return (
      <div className="px-5 py-3.5 glass border-b border-[hsl(var(--border))] animate-fade-in">
        <div className="flex items-center justify-center gap-2.5 text-sm text-[hsl(var(--muted-foreground))]">
          <div className="relative flex items-center justify-center w-5 h-5">
            <div className="absolute inset-0 rounded-full border border-blue-500/20 animate-ping" style={{ animationDuration: "1.5s" }} />
            <Loader2 className="w-4 h-4 animate-spin text-blue-400" />
          </div>
          <span className="animate-pulse-soft">Interpreting your query...</span>
        </div>
      </div>
    );
  }

  if (!suggestions || suggestions.length === 0) return null;

  const modeLabel = mode === "deep_dive" ? "company" : "sector";

  return (
    <div className="px-5 py-3.5 glass border-b border-[hsl(var(--border))] animate-fade-in">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <div className="flex items-center justify-center w-5 h-5 rounded-md bg-blue-500/10">
              <Sparkles className="w-3 h-3 text-blue-400" />
            </div>
            <p className="text-xs font-medium text-[hsl(var(--muted-foreground))]">
              Did you mean? Select a {modeLabel} to search:
            </p>
          </div>
          <button
            type="button"
            onClick={onDismiss}
            aria-label="Dismiss suggestions"
            className="p-1 rounded-md hover:bg-[hsl(var(--muted))] text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] transition-colors duration-200 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--ring))]"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Suggestion chips */}
        <div className="flex flex-wrap gap-2">
          {suggestions.map((s, i) => (
            <button
              key={s}
              type="button"
              onClick={() => onSelect?.(s)}
              className={cn(
                "group relative px-3.5 py-2 rounded-lg text-sm font-medium cursor-pointer",
                "transition-all duration-200",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50",
                "animate-fade-in-up",
                i === 0
                  ? "bg-blue-500/12 text-blue-400 ring-1 ring-blue-500/25 shadow-sm shadow-blue-500/10 hover:bg-blue-500/20 hover:shadow-md hover:shadow-blue-500/15"
                  : "bg-[hsl(var(--muted))] text-[hsl(var(--foreground))] ring-1 ring-[hsl(var(--border))] hover:ring-blue-500/30 hover:bg-blue-500/8 hover:text-blue-400"
              )}
              style={{ animationDelay: `${i * 60}ms` }}
            >
              {i === 0 && (
                <span className="absolute -top-1.5 -right-1.5 flex h-3.5 w-3.5 items-center justify-center">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-30" style={{ animationDuration: "2s" }} />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-blue-400" />
                </span>
              )}
              {s}
            </button>
          ))}
        </div>

        {/* Use original link */}
        {originalQuery && (
          <button
            type="button"
            onClick={() => onSelect?.(originalQuery)}
            className="mt-3 flex items-center gap-1.5 text-xs text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] transition-colors duration-200 cursor-pointer group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--ring))] rounded"
          >
            <CornerDownRight className="w-3 h-3 opacity-50 group-hover:opacity-80 transition-opacity" />
            <span>
              Use original: <span className="font-medium text-[hsl(var(--foreground))]/60 group-hover:text-[hsl(var(--foreground))]">&ldquo;{originalQuery}&rdquo;</span>
            </span>
          </button>
        )}
      </div>
    </div>
  );
}
