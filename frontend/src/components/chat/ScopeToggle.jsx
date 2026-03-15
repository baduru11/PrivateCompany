import { useState, useEffect } from "react";
import { cn } from "../../lib/utils";
import { getApiUrl } from "../../lib/api";

export function ScopeToggle({ scope, onScopeChange }) {
  const [reportCount, setReportCount] = useState(0);

  useEffect(() => {
    fetch(getApiUrl("/api/chat/status"))
      .then((r) => r.json())
      .then((d) => setReportCount(d.indexed_reports || 0))
      .catch(() => {});
  }, []);

  return (
    <div className="relative flex rounded-xl bg-white/[0.04] p-1">
      {/* Animated slider */}
      <div
        className={cn(
          "absolute inset-y-1 rounded-lg bg-gradient-to-r from-blue-500/15 to-blue-500/10 border border-blue-500/20 transition-all duration-300 ease-out",
          scope === "current"
            ? "left-1 w-[calc(50%-4px)]"
            : "left-[50%] w-[calc(50%-4px)]",
        )}
      />
      <button
        onClick={() => onScopeChange("current")}
        className={cn(
          "relative z-10 flex-1 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors duration-200 cursor-pointer",
          scope === "current" ? "text-blue-400" : "text-muted-foreground hover:text-foreground",
        )}
      >
        This report
      </button>
      <button
        onClick={() => onScopeChange("all")}
        className={cn(
          "relative z-10 flex-1 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors duration-200 cursor-pointer",
          scope === "all" ? "text-blue-400" : "text-muted-foreground hover:text-foreground",
        )}
      >
        All research
        {reportCount > 1 && (
          <span className="ml-1 rounded-full bg-blue-500/15 px-1.5 py-0.5 text-[9px] font-semibold text-blue-400 tabular-nums">
            {reportCount}
          </span>
        )}
      </button>
    </div>
  );
}
