import { cn } from "../../lib/utils";
import { ExternalLink } from "lucide-react";
import SentimentBadge from "../shared/SentimentBadge";

const borderColors = {
  positive: "border-l-emerald-500",
  neutral: "border-l-zinc-500",
  negative: "border-l-red-500",
};

/**
 * News item card with colored left border based on sentiment.
 *
 * Props:
 *  - newsItem: { title, date, snippet, sentiment, source_url }
 */
export default function NewsCard({ newsItem }) {
  if (!newsItem) return null;

  const {
    title,
    date,
    snippet,
    sentiment = "neutral",
    source_url,
  } = newsItem;

  return (
    <div
      className={cn(
        "rounded-md border border-[hsl(var(--border))] border-l-4 bg-[hsl(var(--card))] p-4 space-y-2",
        borderColors[sentiment] || borderColors.neutral
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <h4 className="text-sm font-semibold text-[hsl(var(--foreground))] leading-snug">
            {title}
          </h4>
          {date && (
            <p className="text-xs text-[hsl(var(--muted-foreground))] mt-0.5">
              {date}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <SentimentBadge sentiment={sentiment} />
          {source_url && (
            <a
              href={source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] transition-colors"
              title="View source"
            >
              <ExternalLink className="h-4 w-4" />
            </a>
          )}
        </div>
      </div>
      {snippet && (
        <p className="text-xs text-[hsl(var(--muted-foreground))] leading-relaxed line-clamp-3">
          {snippet}
        </p>
      )}
    </div>
  );
}
