import { AlertTriangle } from "lucide-react";
import ConfidenceBadge from "../shared/ConfidenceBadge";

/**
 * Warning-styled card for red flag items.
 *
 * Props:
 *  - content: string (the red flag description)
 *  - confidence: float 0-1
 *  - sourceUrls: array of { url, snippet? }
 */
export default function RedFlagCard({ content, confidence, sourceUrls = [] }) {
  if (!content) return null;

  return (
    <div className="rounded-md border border-amber-500/30 bg-amber-500/5 p-4 space-y-2">
      <div className="flex items-start gap-3">
        <AlertTriangle className="h-5 w-5 text-amber-400 shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0 space-y-2">
          <p className="text-sm text-[hsl(var(--foreground))] leading-relaxed">
            {content}
          </p>
          {confidence != null && (
            <ConfidenceBadge
              confidence={confidence}
              sourceCount={sourceUrls.length}
              sourceUrls={sourceUrls}
            />
          )}
        </div>
      </div>
    </div>
  );
}
