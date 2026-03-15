import { useState, useRef, useEffect } from "react";
import { X, MessageSquare, Trash2, Sparkles } from "lucide-react";
import { cn } from "../../lib/utils";
import { useChatStream } from "../../hooks/useChatStream";
import { ChatMessage } from "./ChatMessage";
import { ChatInput } from "./ChatInput";
import { ScopeToggle } from "./ScopeToggle";

export function ChatPanel({ reportId, companyName, isOpen, onToggle }) {
  const [scope, setScope] = useState("current");
  const scrollRef = useRef(null);
  const { messages, isStreaming, error, sendMessage, clearMessages } =
    useChatStream(reportId);

  // Auto-scroll on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [messages]);

  const handleSend = (message) => {
    sendMessage(message, { scope, companyName });
  };

  return (
    <>
      {/* Floating popup */}
      <div
        className={cn(
          "fixed bottom-20 right-6 z-50 flex flex-col rounded-2xl shadow-2xl shadow-black/50 transition-all duration-300 ease-out origin-bottom-right",
          "border border-white/[0.1] bg-[hsl(222_47%_6%/0.95)] backdrop-blur-2xl",
          "w-[calc(100vw-2rem)] sm:w-[420px] h-[min(560px,calc(100vh-8rem))]",
          isOpen
            ? "scale-100 opacity-100"
            : "pointer-events-none scale-95 opacity-0",
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-white/[0.08] px-5 py-3.5 shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500/20 to-purple-500/20">
              <Sparkles className="h-3.5 w-3.5 text-blue-400" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-foreground leading-none">
                Research Chat
              </h3>
              {companyName && (
                <p className="text-[10px] text-muted-foreground mt-0.5">{companyName}</p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-0.5">
            {messages.length > 0 && (
              <button
                onClick={clearMessages}
                className="rounded-lg p-2 text-muted-foreground/60 transition-all hover:bg-white/[0.06] hover:text-foreground cursor-pointer"
                title="Clear chat"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            )}
            <button
              onClick={onToggle}
              className="rounded-lg p-2 text-muted-foreground/60 transition-all hover:bg-white/[0.06] hover:text-foreground cursor-pointer"
              title="Close chat"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Scope Toggle */}
        <div className="px-4 py-2.5 shrink-0 border-b border-white/[0.04]">
          <ScopeToggle scope={scope} onScopeChange={setScope} />
        </div>

        {/* Messages */}
        <div
          ref={scrollRef}
          className="flex flex-1 flex-col gap-4 overflow-y-auto px-4 py-4 min-h-0"
        >
          {messages.length === 0 && (
            <div className="flex flex-1 flex-col items-center justify-center gap-4 text-center px-4">
              <div className="relative">
                <div className="absolute inset-0 rounded-full bg-blue-500/10 animate-ping" style={{ animationDuration: "3s" }} />
                <div className="relative rounded-full bg-gradient-to-br from-blue-500/15 to-purple-500/15 p-4">
                  <MessageSquare className="h-7 w-7 text-blue-400" />
                </div>
              </div>
              <div className="space-y-1.5">
                <p className="text-sm font-medium text-foreground">
                  Ask anything about this research
                </p>
                <p className="text-xs text-muted-foreground leading-relaxed max-w-[260px]">
                  I can answer questions using the collected data, or search the web for the latest information.
                </p>
              </div>
              <div className="flex flex-wrap justify-center gap-1.5 mt-1">
                {["Key competitors?", "Revenue growth?", "Recent news?"].map((q) => (
                  <button
                    key={q}
                    onClick={() => handleSend(q)}
                    className="rounded-full border border-white/[0.08] bg-white/[0.03] px-3 py-1 text-[11px] text-muted-foreground hover:bg-white/[0.08] hover:text-foreground transition-all cursor-pointer"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map((msg, i) => (
            <ChatMessage key={i} message={msg} index={i} />
          ))}
          {error && (
            <div className="rounded-xl bg-red-500/10 border border-red-500/20 px-4 py-2.5 text-xs text-red-400">
              {error}
            </div>
          )}
        </div>

        {/* Input */}
        <div className="border-t border-white/[0.08] px-4 py-3 shrink-0 bg-white/[0.02]">
          <ChatInput onSend={handleSend} disabled={isStreaming} />
        </div>
      </div>

      {/* Toggle button — always visible */}
      <button
        onClick={onToggle}
        className={cn(
          "fixed bottom-6 right-6 z-50 flex items-center justify-center rounded-full shadow-lg transition-all duration-300 cursor-pointer",
          "active:scale-90",
          isOpen
            ? "h-11 w-11 bg-white/[0.08] border border-white/[0.12] text-foreground hover:bg-white/[0.12] rotate-0"
            : "h-13 w-13 bg-gradient-to-br from-blue-500 to-blue-600 text-white shadow-blue-500/25 hover:shadow-xl hover:shadow-blue-500/35 hover:scale-110",
        )}
        title={isOpen ? "Close chat" : "Ask about this research"}
      >
        {isOpen ? (
          <X className="h-4 w-4" />
        ) : (
          <MessageSquare className="h-5 w-5" />
        )}
      </button>
    </>
  );
}
