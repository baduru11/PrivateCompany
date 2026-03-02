import { CheckCircle2 } from "lucide-react";
import { cn } from "../../lib/utils";

const DEFAULT_STEPS = ["Validating", "Planner", "Searcher", "Profiler", "Synthesis", "Critic"];

/**
 * Horizontal row of pipeline steps. Active step is highlighted,
 * completed steps show a check icon. Sits below the progress bar.
 */
export default function StepIndicator({
  currentStep = 0,
  steps = DEFAULT_STEPS,
}) {
  return (
    <div className="flex items-center justify-center gap-1 px-4 py-2 bg-[hsl(var(--background))] border-b border-[hsl(var(--border))]">
      {steps.map((step, i) => {
        const isCompleted = i < currentStep;
        const isActive = i === currentStep;

        return (
          <div key={step} className="flex items-center">
            {i > 0 && (
              <div
                className={cn(
                  "w-6 h-px mx-1",
                  isCompleted
                    ? "bg-[hsl(217,91%,60%)]"
                    : "bg-[hsl(var(--border))]"
                )}
              />
            )}
            <div
              className={cn(
                "flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium transition-all duration-300",
                isActive &&
                  "bg-[hsl(217,91%,60%)]/15 text-[hsl(217,91%,60%)] ring-1 ring-[hsl(217,91%,60%)]/30",
                isCompleted && "text-[hsl(142,71%,45%)]",
                !isActive &&
                  !isCompleted &&
                  "text-[hsl(var(--muted-foreground))]"
              )}
            >
              {isCompleted ? (
                <CheckCircle2 className="w-3.5 h-3.5" />
              ) : (
                <span
                  className={cn(
                    "w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-semibold border",
                    isActive
                      ? "border-[hsl(217,91%,60%)] text-[hsl(217,91%,60%)]"
                      : "border-[hsl(var(--border))] text-[hsl(var(--muted-foreground))]"
                  )}
                >
                  {i + 1}
                </span>
              )}
              <span>{step}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
