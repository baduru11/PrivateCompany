import { CheckCircle2 } from "lucide-react";
import { cn } from "../../lib/utils";

const DEFAULT_STEPS = ["Validating", "Planner", "Searcher", "Profiler", "Synthesis", "Critic"];

export default function StepIndicator({
  currentStep = 0,
  steps = DEFAULT_STEPS,
}) {
  return (
    <div className="flex items-center justify-center gap-1 px-4 py-2.5 glass border-b border-[hsl(var(--border))] animate-fade-in">
      {steps.map((step, i) => {
        const isCompleted = i < currentStep;
        const isActive = i === currentStep;

        return (
          <div key={step} className="flex items-center">
            {i > 0 && (
              <div
                className={cn(
                  "w-8 h-px mx-1 transition-colors duration-500",
                  isCompleted
                    ? "bg-blue-500"
                    : "bg-[hsl(var(--border))]"
                )}
              />
            )}
            <div
              className={cn(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-300",
                isActive &&
                  "bg-blue-500/12 text-blue-400 ring-1 ring-blue-500/25 shadow-sm shadow-blue-500/10",
                isCompleted && "text-emerald-400",
                !isActive &&
                  !isCompleted &&
                  "text-[hsl(var(--muted-foreground))]"
              )}
            >
              {isCompleted ? (
                <CheckCircle2 className="w-3.5 h-3.5 animate-scale-in" />
              ) : (
                <span
                  className={cn(
                    "w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-semibold border transition-all duration-300",
                    isActive
                      ? "border-blue-500/50 text-blue-400 bg-blue-500/8 animate-pulse-soft"
                      : "border-[hsl(var(--border))] text-[hsl(var(--muted-foreground))]"
                  )}
                >
                  {i + 1}
                </span>
              )}
              <span className="hidden sm:inline">{step}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
