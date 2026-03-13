import { useState } from "react";
import { Trash2, Network, FileSearch } from "lucide-react";
import { Badge } from "../ui/badge";
import { cn } from "../../lib/utils";

export default function HistoryCard({ report, onSelect, onDelete }) {
  const [confirmDelete, setConfirmDelete] = useState(false);
  const mode = report.mode || "explore";
  const isDeepDive = mode === "deep_dive";

  const formatDate = (dateStr) => {
    if (!dateStr) return "";
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return dateStr;
    }
  };

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => !confirmDelete && onSelect?.(report)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          if (!confirmDelete) onSelect?.(report);
        }
      }}
      className={cn(
        "group relative cursor-pointer rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5 space-y-3",
        "transition-all duration-200 hover-glow",
        "hover:bg-[hsl(var(--accent))]/50",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--primary))]"
      )}
    >
      {/* Top row: mode badge + delete button */}
      <div className="flex items-start justify-between gap-2">
        <Badge
          variant="outline"
          className={cn(
            "text-[10px] font-medium flex items-center gap-1",
            isDeepDive
              ? "bg-purple-500/12 text-purple-400 border-purple-500/25"
              : "bg-blue-500/12 text-blue-400 border-blue-500/25"
          )}
        >
          {isDeepDive ? (
            <FileSearch className="w-3 h-3" />
          ) : (
            <Network className="w-3 h-3" />
          )}
          {isDeepDive ? "Deep Dive" : "Explore"}
        </Badge>

        {/* Delete control */}
        {confirmDelete ? (
          <div className="flex items-center gap-1 animate-fade-in">
            <span className="text-[10px] text-red-400">Delete?</span>
            <button
              type="button"
              className="text-[10px] font-semibold text-red-400 hover:text-red-300 px-1.5 py-0.5 rounded hover:bg-red-500/10 transition-colors cursor-pointer"
              onClick={(e) => {
                e.stopPropagation();
                onDelete?.(report.filename);
              }}
            >
              Yes
            </button>
            <button
              type="button"
              className="text-[10px] text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] px-1.5 py-0.5 rounded hover:bg-[hsl(var(--muted))] transition-colors cursor-pointer"
              onClick={(e) => {
                e.stopPropagation();
                setConfirmDelete(false);
              }}
            >
              No
            </button>
          </div>
        ) : (
          <button
            type="button"
            aria-label="Delete report"
            className="opacity-0 group-hover:opacity-100 transition-all p-1.5 rounded-md text-[hsl(var(--muted-foreground))] hover:text-red-400 hover:bg-red-500/10 cursor-pointer"
            onClick={(e) => {
              e.stopPropagation();
              setConfirmDelete(true);
            }}
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {/* Query name */}
      <h3 className="text-sm font-semibold text-[hsl(var(--foreground))] leading-snug line-clamp-2 group-hover:text-[hsl(var(--primary))] transition-colors">
        {report.query || "Untitled Query"}
      </h3>

      {/* Date */}
      <p className="text-xs text-[hsl(var(--muted-foreground))]">
        {formatDate(report.cached_at)}
      </p>
    </div>
  );
}
