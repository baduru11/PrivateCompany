import { Card, CardHeader, CardTitle, CardContent } from "../ui/card";
import { cn } from "../../lib/utils";
import ConfidenceBadge from "../shared/ConfidenceBadge";

const borderColorMap = {
  high: "border-t-emerald-500/60",
  medium: "border-t-amber-500/60",
  low: "border-t-red-500/60",
};

function getBorderClass(confidence) {
  if (confidence >= 0.7) return borderColorMap.high;
  if (confidence >= 0.4) return borderColorMap.medium;
  return borderColorMap.low;
}

/**
 * Reusable report section card with confidence header and scroll anchor.
 *
 * Props:
 *  - id: string (scroll anchor id)
 *  - title: string
 *  - confidence: float 0-1
 *  - sourceCount: int
 *  - sourceUrls: array of { url, snippet? }
 *  - children: section content
 *  - className: optional extra classes
 */
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
    <section id={id} className="scroll-mt-6">
      <Card
        className={cn(
          "border-t-2",
          hasBadge ? getBorderClass(confidence) : "border-t-[hsl(var(--border))]",
          className
        )}
      >
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
          <CardTitle className="text-lg font-semibold text-[hsl(var(--foreground))]">
            {title}
          </CardTitle>
          {hasBadge && (
            <ConfidenceBadge
              confidence={confidence}
              sourceCount={sourceCount}
              sourceUrls={sourceUrls}
            />
          )}
        </CardHeader>
        <CardContent>{children}</CardContent>
      </Card>
    </section>
  );
}
