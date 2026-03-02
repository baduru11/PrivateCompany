import { useState, useCallback, useEffect } from "react";
import { getApiUrl } from "../lib/api";

const STORAGE_KEY = "agentQuery_lastResult";

function loadFromStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function saveToStorage(query, mode, result) {
  try {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ query, mode, result })
    );
  } catch {
    // ignore quota errors
  }
}

export function useAgentQuery() {
  const saved = loadFromStorage();
  const [query, setQuery] = useState(saved?.query || "");
  const [mode, setMode] = useState(saved?.mode || "explore");
  const [result, setResult] = useState(saved?.result || null);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [events, setEvents] = useState([]);

  // Persist completed results to localStorage
  useEffect(() => {
    if (result && query) {
      saveToStorage(query, mode, result);
    }
  }, [result, query, mode]);

  const submit = useCallback(async (q, m) => {
    setQuery(q);
    setMode(m);
    setResult(null);
    setError(null);
    setIsLoading(true);
    setEvents([]);

    try {
      // Tier 3: LLM semantic pre-check (fast feedback, 1 API call)
      setEvents([{ node: "validation", status: "running", detail: "Validating query...", timestamp: new Date().toISOString() }]);
      try {
        const valResp = await fetch(getApiUrl("/api/validate"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: q }),
        });
        if (valResp.ok) {
          const validation = await valResp.json();
          if (!validation.is_valid) {
            setError(
              validation.reason +
                (validation.suggestion ? ` ${validation.suggestion}` : "")
            );
            setIsLoading(false);
            return;
          }
        }
        // If /api/validate returns a server error (500), fail-open and proceed
      } catch {
        // Network error (server unreachable) — stop here, don't call /api/query
        setError("Cannot reach the server. Is the backend running?");
        setIsLoading(false);
        return;
      }
      setEvents((prev) => [...prev, { node: "validation", status: "complete", detail: "Query validated", timestamp: new Date().toISOString() }]);

      // POST to check cache — response is either JSON (cache hit) or SSE stream
      const resp = await fetch(getApiUrl("/api/query"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q, mode: m }),
      });

      const contentType = resp.headers.get("content-type") || "";

      if (contentType.includes("application/json")) {
        const raw = await resp.json();

        // Handle validation errors (422) and other HTTP errors
        if (!resp.ok) {
          const msg = raw.detail
            || (raw.message)
            || `Request failed (${resp.status})`;
          setError(typeof msg === "string" ? msg : JSON.stringify(msg));
          setIsLoading(false);
          return;
        }

        // Cached result returned directly as JSON
        // API shape: { cached: true, data: { report: {...}, critic: {...} } }
        // Normalize to match SSE complete shape: { report: {...}, critic: {...} }
        const normalized = raw.cached && raw.data ? raw.data : raw;
        setResult(normalized);
        setIsLoading(false);
        return;
      }

      // SSE stream via fetch + ReadableStream (POST can't use EventSource)
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let currentEvent = ""; // tracks the "event:" field

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("event:")) {
            currentEvent = line.slice(6).trim();
          } else if (line.startsWith("data:")) {
            try {
              const data = JSON.parse(line.slice(5).trim());
              const eventType = currentEvent || data.event || "";

              if (eventType === "status") {
                setEvents((prev) => [...prev, { ...data, timestamp: data.timestamp || new Date().toISOString() }]);
              } else if (eventType === "complete") {
                setResult(data);
                setIsLoading(false);
              } else if (eventType === "error") {
                setError(data.error || data.message || "Unknown error");
                setIsLoading(false);
              }
            } catch {
              // ignore malformed SSE lines
            }
            currentEvent = ""; // reset after processing data
          }
        }
      }

      // If stream ended without a complete/error event, mark as done
      setIsLoading(false);
    } catch (err) {
      setError(err.message);
      setIsLoading(false);
    }
  }, []);

  return {
    query,
    mode,
    result,
    error,
    isLoading,
    events,
    submit,
  };
}
