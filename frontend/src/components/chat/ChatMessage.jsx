import { cn } from "../../lib/utils";
import MarkdownProse from "../shared/MarkdownProse";
import { Globe, ExternalLink, Bot, User } from "lucide-react";

export function ChatMessage({ message, index }) {
  const isUser = message.role === "user";

  return (
    <div
      className={cn(
        "flex w-full gap-2.5 animate-init animate-chat-fade-up",
        isUser ? "flex-row-reverse" : "flex-row",
      )}
      style={{ animationDelay: `${index * 0.05}s` }}
    >
      {/* Avatar */}
      <div className={cn(
        "flex h-7 w-7 shrink-0 items-center justify-center rounded-lg mt-0.5",
        isUser
          ? "bg-blue-500/15"
          : "bg-gradient-to-br from-emerald-500/15 to-blue-500/15",
      )}>
        {isUser ? (
          <User className="h-3.5 w-3.5 text-blue-400" />
        ) : (
          <Bot className="h-3.5 w-3.5 text-emerald-400" />
        )}
      </div>

      {/* Message bubble */}
      <div
        className={cn(
          "max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed",
          isUser
            ? "bg-blue-500/12 text-foreground rounded-tr-md"
            : "bg-white/[0.04] border border-white/[0.06] text-foreground rounded-tl-md",
        )}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap">{message.content}</p>
        ) : (
          <>
            {message.isStreaming && !message.content && <TypingIndicator />}
            {message.content && (
              <MarkdownProse content={message.content} citations={[]} />
            )}
            {message.webSearch && (
              <div className="mt-2.5 flex items-center gap-1.5 rounded-lg bg-blue-500/8 px-2.5 py-1.5 text-xs text-blue-400">
                <Globe className="h-3 w-3" />
                <span className="font-medium">Searched the web</span>
                {message.searchQuery && (
                  <span className="text-blue-400/60 truncate max-w-[200px]">
                    &middot; {message.searchQuery}
                  </span>
                )}
              </div>
            )}
            {message.sources?.length > 0 && !message.isStreaming && (
              <div className="mt-3 border-t border-white/[0.06] pt-2.5">
                <p className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground/70">
                  Sources
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {message.sources.map((url, i) => {
                    let hostname;
                    try { hostname = new URL(url).hostname.replace("www.", ""); } catch { hostname = url; }
                    return (
                      <a
                        key={i}
                        href={url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 rounded-md bg-white/[0.04] border border-white/[0.06] px-2 py-1 text-[11px] text-blue-400/80 transition-all hover:bg-blue-500/10 hover:text-blue-400 hover:border-blue-500/20"
                      >
                        <ExternalLink className="h-2.5 w-2.5" />
                        {hostname}
                      </a>
                    );
                  })}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex items-center gap-1.5 py-1 px-1">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="h-2 w-2 rounded-full bg-emerald-400/60 animate-chat-dot"
          style={{ animationDelay: `${i * 0.15}s` }}
        />
      ))}
    </div>
  );
}
