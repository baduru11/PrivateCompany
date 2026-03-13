import { AlertTriangle } from "lucide-react";
import ConfidenceBadge from "../shared/ConfidenceBadge";

export default function RedFlagCard({ content, confidence, sourceUrls = [] }) {
  if (!content) return null;

  return (
    <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4 space-y-2 hover:border-amber-500/30 transition-colors">
      <div className="flex items-start gap-3">
        <div className="p-1.5 rounded-lg bg-amber-500/10 shrink-0 mt-0.5">
          <AlertTriangle className="h-4 w-4 text-amber-400" />
        </div>
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
