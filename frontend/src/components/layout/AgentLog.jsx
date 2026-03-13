import { useState, useRef, useEffect } from "react";
import { ChevronUp, ChevronDown, Terminal } from "lucide-react";
import { ScrollArea } from "../ui/scroll-area";
import { Badge } from "../ui/badge";
import { cn } from "../../lib/utils";

export default function AgentLog({
  events = [],
  isActive = false,
  isOpen: controlledOpen,
  onToggle,
}) {
  const [internalOpen, setInternalOpen] = useState(false);
  const isOpen = controlledOpen !== undefined ? controlledOpen : internalOpen;
  const scrollRef = useRef(null);

  const toggle = () => {
    if (onToggle) {
      onToggle();
    } else {
      setInternalOpen((prev) => !prev);
    }
  };

  useEffect(() => {
    if (isOpen && scrollRef.current) {
      scrollRef.current.scrollTop = 0;
    }
  }, [events.length, isOpen]);

  const reversedEvents = [...events].reverse();
  const latestEvent = events.length > 0 ? events[events.length - 1] : null;

  const statusColor = (status) => {
    switch (status) {
      case "running":
      case "in_progress":
        return "bg-blue-500/15 text-blue-400 border-blue-500/25";
      case "complete":
      case "completed":
      case "done":
        return "bg-emerald-500/15 text-emerald-400 border-emerald-500/25";
      case "error":
      case "failed":
        return "bg-red-500/15 text-red-400 border-red-500/25";
      default:
        return "bg-[hsl(var(--muted))] text-[hsl(var(--muted-foreground))]";
    }
  };

  const formatTime = (timestamp) => {
    if (!timestamp) return "";
    try {
      const d = new Date(timestamp);
      return d.toLocaleTimeString("en-US", {
        hour12: false,
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
    } catch {
      return "";
    }
  };

  // Don't render if no events and not active
  if (!isActive && events.length === 0) return null;

  return (
    <div
      className={cn(
        "fixed bottom-0 left-0 right-0 z-40 transition-all duration-300 ease-in-out",
        "glass-strong border-t border-[hsl(var(--border))]",
        isOpen ? "h-72" : "h-10"
      )}
    >
      {/* Toggle button */}
      <button
        onClick={toggle}
        className={cn(
          "flex items-center gap-2 w-full h-10 px-4 text-xs font-medium",
          "text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]",
          "transition-colors cursor-pointer",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[hsl(var(--ring))]"
        )}
      >
        <Terminal className="w-3.5 h-3.5" />
        <span className="font-semibold">Agent Log</span>
        {events.length > 0 && (
          <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-5 font-mono">
            {events.length}
          </Badge>
        )}

        {latestEvent && (
          <span className="flex items-center gap-1.5 ml-2 text-[11px] text-[hsl(var(--muted-foreground))] truncate max-w-sm">
            {isActive && (
              <span className="relative flex h-2 w-2 shrink-0">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-500 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500" />
              </span>
            )}
            <span className="truncate">
              {latestEvent.node && (
                <span className="font-mono text-blue-400/70">{latestEvent.node}</span>
              )}
              {latestEvent.node && latestEvent.detail && <span className="opacity-40 mx-1">/</span>}
              {latestEvent.detail || latestEvent.message || ""}
            </span>
          </span>
        )}

        <div className="flex-1" />
        {isOpen ? (
          <ChevronDown className="w-3.5 h-3.5" />
        ) : (
          <ChevronUp className="w-3.5 h-3.5" />
        )}
      </button>

      {/* Event list */}
      {isOpen && (
        <ScrollArea className="h-[calc(100%-2.5rem)] px-4 pb-2">
          <div ref={scrollRef} className="space-y-0.5">
            {reversedEvents.length === 0 ? (
              <p className="text-xs text-[hsl(var(--muted-foreground))] py-6 text-center">
                No events yet. Submit a query to see agent activity.
              </p>
            ) : (
              reversedEvents.map((evt, i) => (
                <div
                  key={`${evt.node || ""}-${evt.timestamp || i}`}
                  className="flex items-start gap-3 py-2 text-xs border-b border-[hsl(var(--border))]/30 last:border-0 animate-fade-in"
                  style={{ animationDelay: `${Math.min(i * 0.03, 0.3)}s` }}
                >
                  <span className="text-[10px] font-mono text-[hsl(var(--muted-foreground))]/60 shrink-0 w-16 pt-0.5 tabular-nums">
                    {formatTime(evt.timestamp)}
                  </span>
                  <Badge
                    variant="outline"
                    className={cn(
                      "text-[10px] px-1.5 py-0 h-5 shrink-0 font-mono rounded-md",
                      statusColor(evt.status)
                    )}
                  >
                    {evt.node || evt.step || "system"}
                  </Badge>
                  <span className="text-[hsl(var(--foreground))]/70 flex-1 leading-relaxed">
                    {evt.detail || evt.message || JSON.stringify(evt)}
                  </span>
                </div>
              ))
            )}
          </div>
        </ScrollArea>
      )}
    </div>
  );
}
