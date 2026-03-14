import { useState, useCallback, useEffect, useRef } from "react";
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

  // Suggestion state (Phase 1)
  const [suggestions, setSuggestions] = useState(null);
  const [suggestionsLoading, setSuggestionsLoading] = useState(false);

  // Abort controller for cancelling in-flight requests
  const abortRef = useRef(null);
  // Secondary cancel flag — SSE readers may not throw on abort in all browsers
  const cancelledRef = useRef(false);

  // Persist completed results to localStorage
  useEffect(() => {
    if (result && query) {
      saveToStorage(query, mode, result);
    }
  }, [result, query, mode]);

  // Phase 2: run the pipeline with a confirmed query
  const runPipeline = useCallback(async (q, m) => {
    // Cancel any previous in-flight request
    if (abortRef.current) abortRef.current.abort();
    cancelledRef.current = false;
    const controller = new AbortController();
    abortRef.current = controller;

    setIsLoading(true);
    setEvents([{ node: "validation", status: "complete", detail: "Query validated", timestamp: new Date().toISOString() }]);

    try {
      // POST to check cache — response is either JSON (cache hit) or SSE stream
      const resp = await fetch(getApiUrl("/api/query"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q, mode: m }),
        signal: controller.signal,
      });

      const contentType = resp.headers.get("content-type") || "";


      if (contentType.includes("application/json")) {
        const raw = await resp.json();

        if (!resp.ok) {
          let msg = raw.detail || raw.message || `Request failed (${resp.status})`;
          // FastAPI 422 returns detail as array of validation errors
          if (Array.isArray(msg)) {
            msg = msg.map((e) => e.msg || e.message || JSON.stringify(e)).join("; ");
          }
          setError(typeof msg === "string" ? msg : JSON.stringify(msg));
          setIsLoading(false);
          return;
        }

        const normalized = raw.cached && raw.data ? raw.data : raw;

        setResult(normalized);
        setIsLoading(false);
        return;
      }

      // SSE stream
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let currentEvent = "";
      let receivedComplete = false;

      const processLines = (lines) => {
        for (const line of lines) {
          if (line.startsWith("event:")) {
            currentEvent = line.slice(6).trim();
          } else if (line.startsWith("data:")) {
            try {
              const data = JSON.parse(line.slice(5).trim());
              const eventType = currentEvent || data.event || "";

              if (eventType === "section") {
                setEvents((prev) => [...prev, { ...data, type: "section", timestamp: new Date().toISOString() }]);
              } else if (eventType === "status") {
                setEvents((prev) => [...prev, { ...data, timestamp: data.timestamp || new Date().toISOString() }]);
              } else if (eventType === "complete") {

                setResult(data);
                setIsLoading(false);
                receivedComplete = true;
              } else if (eventType === "error") {

                setError(data.error || data.message || "Unknown error");
                setIsLoading(false);
                receivedComplete = true;
              }
            } catch {
              // ignore malformed SSE lines
            }
            currentEvent = "";
          }
        }
      };

      while (true) {
        if (cancelledRef.current) {
          reader.cancel();
          break;
        }

        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        processLines(lines);
      }

      // Process any remaining data left in the buffer
      if (buffer.trim()) {
        processLines(buffer.split("\n"));
      }

      if (!cancelledRef.current && !receivedComplete) {
        setError("Connection lost — the pipeline did not return a result. Please retry.");
        setIsLoading(false);
      }
    } catch (err) {
      if (err.name === "AbortError" || cancelledRef.current) return; // cancelled by user
      setError(err.message);
      setIsLoading(false);
    }
  }, []);

  // Phase 1: submit → suggest → wait for pick (or auto-proceed)
  const submit = useCallback(async (q, m) => {
    // Cancel any previous in-flight request
    if (abortRef.current) abortRef.current.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setQuery(q);
    setMode(m);
    setResult(null);
    setError(null);
    setSuggestions(null);
    setIsLoading(false);
    setEvents([]);
    setSuggestionsLoading(true);

    try {
      setEvents([{ node: "validation", status: "running", detail: "Validating query...", timestamp: new Date().toISOString() }]);

      const suggestResp = await fetch(getApiUrl("/api/suggest"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q, mode: m }),
        signal: controller.signal,
      });

      if (!suggestResp.ok) {
        // Server error on suggest — fail-open, run pipeline directly
        setSuggestionsLoading(false);
        await runPipeline(q, m);
        return;
      }

      const suggestion = await suggestResp.json();

      if (!suggestion.is_valid) {
        setError(suggestion.reason || "Invalid query.");
        setSuggestionsLoading(false);
        return;
      }

      // Always show suggestions — even high-confidence queries may have
      // name collisions (e.g. "Cluely" vs "Cluely Learning")
      setSuggestions(suggestion);
      setSuggestionsLoading(false);
    } catch (err) {
      if (err.name === "AbortError") return; // cancelled by user
      setSuggestionsLoading(false);
      setError("Cannot reach the server. Is the backend running?");
    }
  }, [runPipeline]);

  // User picks a suggestion (or original query)
  const confirmQuery = useCallback(async (selectedQuery) => {
    setSuggestions(null);
    setSuggestionsLoading(false);
    setQuery(selectedQuery);
    await runPipeline(selectedQuery, mode);
  }, [mode, runPipeline]);

  const dismissSuggestions = useCallback(() => {
    setSuggestions(null);
    setSuggestionsLoading(false);
  }, []);

  const cancel = useCallback(() => {
    // Set cancel flag first — SSE loop checks this
    cancelledRef.current = true;
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setIsLoading(false);
    setSuggestionsLoading(false);
    setSuggestions(null);
    setEvents((prev) => [
      ...prev,
      { node: "system", status: "complete", detail: "Cancelled by user", timestamp: new Date().toISOString() },
    ]);
  }, []);

  return {
    query,
    mode,
    result,
    error,
    isLoading,
    events,
    submit,
    cancel,
    suggestions,
    suggestionsLoading,
    confirmQuery,
    dismissSuggestions,
  };
}
