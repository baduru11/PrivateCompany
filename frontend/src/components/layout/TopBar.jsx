import { useState, useCallback } from "react";
import { Search, Loader2 } from "lucide-react";
import { Input } from "../ui/input";
import { Button } from "../ui/button";
import { Tabs, TabsList, TabsTrigger } from "../ui/tabs";
import { cn } from "../../lib/utils";

const CONSONANTS = new Set("bcdfghjklmnpqrstvwxyz");

/**
 * Tier 1 — instant, client-side rule-based query validation.
 * Returns an error string or null if valid.
 */
function validateQuery(query) {
  const q = query.trim();

  if (q.length < 3) return "Query is too short (minimum 3 characters).";
  if (q.length > 200) return "Query is too long (maximum 200 characters).";
  if (!/[a-zA-Z0-9]/.test(q)) return "Query must contain letters or numbers.";
  if (/(.)\1{3,}/.test(q)) return "Query contains too many repeated characters.";

  // Keyboard mash: 5+ consecutive consonants
  let consec = 0;
  for (const ch of q.toLowerCase()) {
    if (CONSONANTS.has(ch)) {
      consec += 1;
      if (consec >= 5) return "Query looks like random keyboard input.";
    } else {
      consec = 0;
    }
  }

  // At least 40% alphabetic
  const alphaCount = [...q].filter((ch) => /[a-zA-Z]/.test(ch)).length;
  if (q.length > 0 && alphaCount / q.length < 0.4)
    return "Query must be mostly text, not numbers or symbols.";

  return null;
}

/**
 * Compact top bar: logo on left, search input in center,
 * mode toggle (Explore / Deep Dive), and submit button.
 * Bloomberg-style — data-focused, not chatbot-like.
 */
export default function TopBar({ onSubmit, isLoading = false, onLogoClick }) {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState("explore");
  const [validationError, setValidationError] = useState(null);

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
    <header className="flex items-center gap-4 px-4 py-2 bg-[hsl(var(--card))] border-b border-[hsl(var(--border))]">
      {/* Logo — click to return to history */}
      <button
        type="button"
        onClick={onLogoClick}
        className="flex items-center gap-2 shrink-0 cursor-pointer hover:opacity-80 transition-opacity"
      >
        <div className="w-7 h-7 rounded bg-[hsl(217,91%,60%)] flex items-center justify-center">
          <span className="text-white text-xs font-bold">CI</span>
        </div>
        <span className="text-sm font-semibold text-[hsl(var(--foreground))] tracking-tight hidden sm:inline">
          CompanyIntel
        </span>
      </button>

      {/* Search form */}
      <form
        onSubmit={handleSubmit}
        className="flex items-center gap-2 flex-1 max-w-2xl mx-auto"
      >
        <div className="relative flex-1">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[hsl(var(--muted-foreground))]" />
          <Input
            value={query}
            onChange={handleChange}
            placeholder="e.g. AI infrastructure startups in Series A-B..."
            className={cn(
              "pl-8 h-9 text-sm bg-[hsl(var(--background))]",
              validationError
                ? "border-red-500 focus-visible:ring-red-500/40"
                : "border-[hsl(var(--border))] focus-visible:ring-[hsl(217,91%,60%)]/40"
            )}
            disabled={isLoading}
          />
          {validationError && (
            <p className="absolute left-0 top-full mt-1 text-xs text-red-500">
              {validationError}
            </p>
          )}
        </div>

        {/* Mode toggle */}
        <Tabs value={mode} onValueChange={setMode} className="shrink-0">
          <TabsList className="h-9">
            <TabsTrigger value="explore" className="text-xs px-3 h-7">
              Explore
            </TabsTrigger>
            <TabsTrigger value="deep_dive" className="text-xs px-3 h-7">
              Deep Dive
            </TabsTrigger>
          </TabsList>
        </Tabs>

        {/* Submit */}
        <Button
          type="submit"
          size="sm"
          disabled={isLoading || !query.trim()}
          className="h-9 px-4 bg-[hsl(217,91%,60%)] hover:bg-[hsl(217,91%,50%)] text-white shrink-0"
        >
          {isLoading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            "Query"
          )}
        </Button>
      </form>

      {/* Right spacer for balance */}
      <div className="w-24 shrink-0 hidden sm:block" />
    </header>
  );
}
