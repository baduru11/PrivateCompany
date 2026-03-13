import { useState, useCallback, useEffect } from "react";
import { Search, Loader2, Sparkles, Square } from "lucide-react";
import { Input } from "../ui/input";
import { Button } from "../ui/button";
import { cn } from "../../lib/utils";

const CONSONANTS = new Set("bcdfghjklmnpqrstvwxz"); // 'y' excluded — acts as vowel in crypto, gym, etc.

function validateQuery(query) {
  const q = query.trim();
  if (q.length < 3) return "Query is too short (minimum 3 characters).";
  if (q.length > 200) return "Query is too long (maximum 200 characters).";
  if (!/[a-zA-Z0-9]/.test(q)) return "Query must contain letters or numbers.";
  if (/(.)\1{3,}/.test(q)) return "Query contains too many repeated characters.";
  let consec = 0;
  for (const ch of q.toLowerCase()) {
    if (CONSONANTS.has(ch)) {
      consec += 1;
      if (consec >= 5) return "Query looks like random keyboard input.";
    } else {
      consec = 0;
    }
  }
  const alphaCount = [...q].filter((ch) => /[a-zA-Z]/.test(ch)).length;
  if (q.length > 0 && alphaCount / q.length < 0.4)
    return "Query must be mostly text, not numbers or symbols.";
  return null;
}

export default function TopBar({ onSubmit, isLoading = false, onLogoClick, onCancel, externalQuery }) {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState("explore");
  const [validationError, setValidationError] = useState(null);

  // Sync input when a suggestion is selected
  useEffect(() => {
    if (externalQuery) {
      setQuery(externalQuery);
    }
  }, [externalQuery]);

  const handleChange = useCallback((e) => {
    setQuery(e.target.value);
    setValidationError(null);
  }, []);

  const handleSubmit = useCallback(
    (e) => {
      e.preventDefault();
      const trimmed = query.trim();
      if (!trimmed || isLoading) return;
      const error = validateQuery(trimmed);
      if (error) {
        setValidationError(error);
        return;
      }
      setValidationError(null);
      onSubmit?.(trimmed, mode);
    },
    [query, mode, isLoading, onSubmit]
  );

  return (
    <header className="relative flex items-center gap-4 px-5 py-2.5 glass-strong border-b border-[hsl(var(--border))] z-20">
      {/* Logo */}
      <button
        type="button"
        onClick={onLogoClick}
        className="flex items-center gap-2.5 shrink-0 cursor-pointer group rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--ring))]"
      >
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center shadow-lg shadow-blue-500/20 group-hover:shadow-blue-500/30 transition-shadow">
          <Sparkles className="w-4 h-4 text-white" />
        </div>
        <span className="text-sm font-bold text-[hsl(var(--foreground))] tracking-tight hidden sm:inline group-hover:text-[hsl(var(--primary))] transition-colors">
          CompanyIntel
        </span>
      </button>

      {/* Search form */}
      <form
        onSubmit={handleSubmit}
        className="flex items-center gap-2.5 flex-1 max-w-2xl mx-auto"
      >
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[hsl(var(--muted-foreground))]" />
          <Input
            value={query}
            onChange={handleChange}
            placeholder="e.g. AI infrastructure startups in Series A-B..."
            className={cn(
              "pl-9 h-10 text-sm bg-[hsl(var(--background))] rounded-lg",
              "border-[hsl(var(--border))] transition-all duration-200",
              validationError
                ? "border-red-500 focus-visible:ring-red-500/40"
                : "focus-visible:ring-[hsl(var(--primary))]/40 focus-visible:border-[hsl(var(--primary))]/50"
            )}
            disabled={isLoading}
          />
          {validationError && (
            <p className="absolute left-0 top-full mt-1.5 text-xs text-red-400 animate-fade-in">
              {validationError}
            </p>
          )}
        </div>

        {/* Mode toggle */}
        <div className="flex items-center h-10 rounded-lg bg-[hsl(var(--muted))] p-1 shrink-0">
          {[
            { value: "explore", label: "Explore" },
            { value: "deep_dive", label: "Deep Dive" },
          ].map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => setMode(opt.value)}
              className={cn(
                "px-3.5 py-1.5 rounded-md text-xs font-medium transition-all duration-200 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--ring))]",
                mode === opt.value
                  ? "bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] shadow-sm"
                  : "text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]"
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>

        {/* Submit / Stop */}
        {isLoading ? (
          <Button
            type="button"
            onClick={onCancel}
            className={cn(
              "h-10 px-5 rounded-lg font-medium shrink-0 transition-all duration-200 cursor-pointer",
              "bg-gradient-to-r from-red-500 to-red-600 hover:from-red-600 hover:to-red-700",
              "text-white shadow-lg shadow-red-500/20 hover:shadow-red-500/30"
            )}
          >
            <Square className="w-3.5 h-3.5 mr-1.5 fill-current" />
            Stop
          </Button>
        ) : (
          <Button
            type="submit"
            disabled={!query.trim()}
            className={cn(
              "h-10 px-5 rounded-lg font-medium shrink-0 transition-all duration-200",
              "bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700",
              "text-white shadow-lg shadow-blue-500/20 hover:shadow-blue-500/30",
              "disabled:opacity-50 disabled:shadow-none"
            )}
          >
            Search
          </Button>
        )}
      </form>

      {/* Right spacer for balance */}
      <div className="w-24 shrink-0 hidden sm:block" />
    </header>
  );
}
