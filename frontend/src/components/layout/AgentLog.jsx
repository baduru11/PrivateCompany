import { useState, useRef, useEffect } from "react";
import { ChevronUp, ChevronDown, Terminal } from "lucide-react";
import { ScrollArea } from "../ui/scroll-area";
import { Badge } from "../ui/badge";
import { cn } from "../../lib/utils";

/**
 * Collapsible drawer at bottom of screen showing SSE events
 * in reverse chronological order. Each event shows node name,
 * status, detail text, and timestamp.
 *
 * The toggle bar shows a live status summary when the pipeline is active.
 */
export default function AgentLog({
  events = [],
  isActive = false,
  isOpen: controlledOpen,
  onToggle,
}) {
  // Support both controlled and uncontrolled mode
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

  // Auto-scroll to top (newest) when new events arrive and drawer is open
  useEffect(() => {
    if (isOpen && scrollRef.current) {
      scrollRef.current.scrollTop = 0;
    }
  }, [events.length, isOpen]);

  const reversedEvents = [...events].reverse();

  // Derive the latest event detail for the toggle bar
  const latestEvent = events.length > 0 ? events[events.length - 1] : null;

  const statusColor = (status) => {
    switch (status) {
      case "running":
      case "in_progress":
        return "bg-[hsl(217,91%,60%)]/20 text-[hsl(217,91%,60%)] border-[hsl(217,91%,60%)]/30";
      case "complete":
      case "completed":
      case "done":
        return "bg-[hsl(142,71%,45%)]/20 text-[hsl(142,71%,45%)] border-[hsl(142,71%,45%)]/30";
      case "error":
      case "failed":
        return "bg-[hsl(0,84%,60%)]/20 text-[hsl(0,84%,60%)] border-[hsl(0,84%,60%)]/30";
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

  return (
    <div
      className={cn(
        "fixed bottom-0 left-0 right-0 z-40 transition-all duration-300 ease-in-out",
        "bg-[hsl(var(--card))] border-t border-[hsl(var(--border))]",
        isOpen ? "h-64" : "h-9"
      )}
    >
      {/* Toggle button */}
      <button
        onClick={toggle}
        className={cn(
          "flex items-center gap-2 w-full h-9 px-4 text-xs font-medium",
          "text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]",
          "transition-colors cursor-pointer"
        )}
      >
        <Terminal className="w-3.5 h-3.5" />
        <span>Agent Log</span>
        {events.length > 0 && (
          <span className="text-[10px] text-[hsl(var(--muted-foreground))]">
            ({events.length})
          </span>
        )}

        {/* Live status: show latest event detail + pulsing dot when active */}
        {latestEvent && (
          <span className="flex items-center gap-1.5 ml-2 text-[11px] text-[hsl(var(--muted-foreground))] truncate max-w-xs">
            {isActive && (
              <span className="relative flex h-2 w-2 shrink-0">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[hsl(217,91%,60%)] opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-[hsl(217,91%,60%)]" />
              </span>
            )}
            <span className="truncate">
              {latestEvent.node && (
                <span className="font-mono opacity-60">{latestEvent.node}</span>
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
        <ScrollArea className="h-[calc(100%-2.25rem)] px-4 pb-2">
          <div ref={scrollRef} className="space-y-1">
            {reversedEvents.length === 0 ? (
              <p className="text-xs text-[hsl(var(--muted-foreground))] py-4 text-center">
                No events yet. Submit a query to see agent activity.
              </p>
            ) : (
              reversedEvents.map((evt, i) => (
                <div
                  key={`${evt.node || ""}-${evt.timestamp || i}`}
                  className="flex items-start gap-3 py-1.5 text-xs border-b border-[hsl(var(--border))]/50 last:border-0"
                >
                  <span className="text-[10px] font-mono text-[hsl(var(--muted-foreground))] shrink-0 w-16 pt-0.5">
                    {formatTime(evt.timestamp)}
                  </span>
                  <Badge
                    variant="outline"
                    className={cn(
                      "text-[10px] px-1.5 py-0 h-5 shrink-0 font-mono",
                      statusColor(evt.status)
                    )}
                  >
                    {evt.node || evt.step || "system"}
                  </Badge>
                  <span className="text-[hsl(var(--foreground))]/80 flex-1 leading-relaxed">
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
