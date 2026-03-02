import { cn } from "../../lib/utils";

/**
 * Thin GitHub-style progress bar fixed at the very top of the viewport.
 * Width animates based on currentStep (0-5), with indeterminate shimmer while active.
 */
export default function ProgressBar({ currentStep = 0, isActive = false }) {
  const percent = Math.min((currentStep / 6) * 100, 100);

  if (!isActive && currentStep === 0) return null;

  return (
    <div
      className={cn(
        "fixed top-0 left-0 right-0 z-50 h-[3px] bg-transparent",
        "transition-opacity duration-300",
        !isActive && currentStep >= 6 ? "opacity-0" : "opacity-100"
      )}
    >
      <div
        className="h-full bg-[hsl(217,91%,60%)] transition-[width] duration-700 ease-out relative overflow-hidden"
        style={{ width: `${percent}%` }}
      >
        {isActive && (
          <div
            className="absolute inset-0 animate-shimmer"
            style={{
              background:
                "linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.3) 50%, transparent 100%)",
              backgroundSize: "200% 100%",
            }}
          />
        )}
      </div>
    </div>
  );
}
