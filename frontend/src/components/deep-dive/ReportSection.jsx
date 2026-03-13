import { cn } from "../../lib/utils";
import ConfidenceBadge from "../shared/ConfidenceBadge";

const borderColorMap = {
  high: "border-l-emerald-500/50",
  medium: "border-l-amber-500/50",
  low: "border-l-red-500/50",
};

function getBorderClass(confidence) {
  if (confidence >= 0.7) return borderColorMap.high;
  if (confidence >= 0.4) return borderColorMap.medium;
  return borderColorMap.low;
}

export default function ReportSection({
  id,
  title,
  confidence,
  sourceCount,
  sourceUrls,
  children,
  className,
}) {
  const hasBadge = confidence !== undefined && confidence !== null;

  return (
    <section id={id} className="scroll-mt-8 animate-init animate-fade-in-up" style={{ animationDelay: '0.1s' }}>
      <div
        className={cn(
          "rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] overflow-hidden",
          "border-l-[3px]",
          hasBadge ? getBorderClass(confidence) : "border-l-[hsl(var(--border))]",
          className
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-5 pb-4">
          <h2 className="text-lg font-semibold text-[hsl(var(--foreground))]">
            {title}
          </h2>
          {hasBadge && (
            <ConfidenceBadge
              confidence={confidence}
              sourceCount={sourceCount}
              sourceUrls={sourceUrls}
            />
          )}
        </div>
        {/* Content */}
        <div className="px-5 pb-5">{children}</div>
      </div>
    </section>
  );
}
