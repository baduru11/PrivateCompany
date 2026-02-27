import { cn } from "../../lib/utils";
import SourcePopover from "./SourcePopover";

/**
 * Colored badge showing a confidence score with source count.
 * Clicking opens a SourcePopover with raw source URLs.
 *
 * Props:
 *  - confidence: float 0-1
 *  - sourceCount: int
 *  - sourceUrls: array of { url, snippet? }
 */
function getConfidenceLevel(confidence) {
  if (confidence >= 0.7) return { label: "High Confidence", color: "green" };
  if (confidence >= 0.4) return { label: "Medium Confidence", color: "yellow" };
  return { label: "Low Confidence", color: "red" };
}

const colorClasses = {
  green: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  yellow: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  red: "bg-red-500/15 text-red-400 border-red-500/30",
};

const dotClasses = {
  green: "bg-emerald-400",
  yellow: "bg-amber-400",
  red: "bg-red-400",
};

export default function ConfidenceBadge({
  confidence = 0,
  sourceCount = 0,
  sourceUrls = [],
}) {
  const { label, color } = getConfidenceLevel(confidence);
  const pct = Math.round(confidence * 100);

  const badge = (
    <button
      type="button"
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium transition-colors cursor-pointer hover:opacity-80",
        colorClasses[color]
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", dotClasses[color])} />
      <span>{pct}%</span>
      {sourceCount > 0 && (
        <span className="opacity-70">
          &middot; {sourceCount} source{sourceCount !== 1 ? "s" : ""}
        </span>
      )}
    </button>
  );

  if (sourceUrls && sourceUrls.length > 0) {
    return <SourcePopover sources={sourceUrls}>{badge}</SourcePopover>;
  }

  return badge;
}

// Re-export helper for use by SectionNav dots
export { getConfidenceLevel, dotClasses };
