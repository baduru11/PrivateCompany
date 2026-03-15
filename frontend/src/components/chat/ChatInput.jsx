import { useState, useRef, useEffect } from "react";
import { ArrowUp } from "lucide-react";
import { cn } from "../../lib/utils";

export function ChatInput({ onSend, disabled }) {
  const [value, setValue] = useState("");
  const textareaRef = useRef(null);

  useEffect(() => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = Math.min(el.scrollHeight, 120) + "px";
    }
  }, [value]);

  const handleSubmit = () => {
    if (!value.trim() || disabled) return;
    onSend(value.trim());
    setValue("");
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="relative flex items-end gap-2 rounded-xl border border-white/[0.08] bg-white/[0.03] p-1.5 transition-all duration-200 focus-within:border-blue-500/30 focus-within:bg-white/[0.04] focus-within:shadow-[0_0_0_3px_rgba(59,130,246,0.08)]">
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask about this research..."
        disabled={disabled}
        rows={1}
        className="flex-1 resize-none bg-transparent px-2.5 py-2 text-sm text-foreground placeholder:text-muted-foreground/60 focus:outline-none disabled:opacity-50"
      />
      <button
        onClick={handleSubmit}
        disabled={disabled || !value.trim()}
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg transition-all duration-200 cursor-pointer",
          value.trim() && !disabled
            ? "bg-gradient-to-br from-blue-500 to-blue-600 text-white shadow-sm shadow-blue-500/20 hover:shadow-md hover:shadow-blue-500/30 active:scale-90"
            : "text-muted-foreground/30",
        )}
      >
        <ArrowUp className="h-4 w-4" strokeWidth={2.5} />
      </button>
    </div>
  );
}
