import { cn } from "../../lib/utils";
import { TrendingUp, Minus, TrendingDown } from "lucide-react";

const config = {
  positive: {
    icon: TrendingUp,
    classes: "bg-emerald-500/12 text-emerald-400 border-emerald-500/25",
    label: "Positive",
  },
  neutral: {
    icon: Minus,
    classes: "bg-zinc-500/12 text-zinc-400 border-zinc-500/25",
    label: "Neutral",
  },
  negative: {
    icon: TrendingDown,
    classes: "bg-red-500/12 text-red-400 border-red-500/25",
    label: "Negative",
  },
};

export default function SentimentBadge({ sentiment = "neutral" }) {
  const { icon: Icon, classes, label } = config[sentiment] || config.neutral;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium",
        classes
      )}
    >
      <Icon className="h-3 w-3" />
      {label}
    </span>
  );
}
