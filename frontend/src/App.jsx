import { useState, useCallback, useRef, useMemo } from "react";

// Layout
import TopBar from "./components/layout/TopBar";
import ProgressBar from "./components/layout/ProgressBar";
import StepIndicator from "./components/layout/StepIndicator";
import AgentLog from "./components/layout/AgentLog";

// Views
import HistoryGrid from "./components/history/HistoryGrid";
import ExploreView from "./components/explore/ExploreView";
import DeepDiveView from "./components/deep-dive/DeepDiveView";

// Shared
import { PDFExport } from "./components/shared/PDFExport";

// Hooks
import { useAgentQuery } from "./hooks/useAgentQuery";
import { fetchReport } from "./lib/api";

/**
 * Map SSE event node names to step numbers for StepIndicator.
 */
const NODE_TO_STEP = {
  validation: 1,
  planner: 2,
  searcher: 3,
  profiler: 4,
  synthesis: 5,
  critic: 6,
};

/**
 * Derive the current step from the latest SSE events.
 */
function deriveCurrentStep(events) {
  if (!events || events.length === 0) return 0;
  let maxStep = 0;
  for (const evt of events) {
    const node = (evt.node || evt.step || "").toLowerCase();
    const step = NODE_TO_STEP[node];
    if (step && step > maxStep) {
      maxStep = step;
    }
  }
  return maxStep;
}

/**
 * Main application shell with state-based view routing.
 *
 * Views:
 *  - "history" (landing page): HistoryGrid
 *  - "explore": ExploreView (force graph + sidebar)
 *  - "deep_dive": DeepDiveView (structured report)
 */
function App() {
  // View routing state
  const [currentView, setCurrentView] = useState("history");
  const [queryResult, setQueryResult] = useState(null);

  // Agent log toggle
  const [agentLogOpen, setAgentLogOpen] = useState(false);

  // Ref for PDF export
  const reportRef = useRef(null);

  // Agent query hook
  const { result, error, isLoading, events, submit } = useAgentQuery();

  // Derive current pipeline step from events
  const currentStep = useMemo(() => deriveCurrentStep(events), [events]);

  // When the agent query completes, update the view and result
  // We track the result from the hook and sync it
  const prevResultRef = useRef(null);
  if (result && result !== prevResultRef.current) {
    prevResultRef.current = result;
    // Defer state update to avoid setting state during render
    if (queryResult !== result) {
      // This is intentionally synchronous — React batches it
      setTimeout(() => {
        setQueryResult(result);
      }, 0);
    }
  }

  /**
   * Handle query submission from TopBar.
   */
  const handleSubmit = useCallback(
    (query, mode) => {
      setCurrentView(mode === "deep_dive" ? "deep_dive" : "explore");
      setQueryResult(null);
      setAgentLogOpen(false);
      submit(query, mode);
    },
    [submit]
  );

  /**
   * Handle logo click — return to history view.
   */
  const handleLogoClick = useCallback(() => {
    setCurrentView("history");
    setQueryResult(null);
  }, []);

  /**
   * Handle selecting a report from history.
   */
  const handleSelectReport = useCallback(async (report) => {
    const mode = report.mode || "explore";
    try {
      const fullReport = await fetchReport(report.filename);
      setQueryResult(fullReport);
      setCurrentView(mode === "deep_dive" ? "deep_dive" : "explore");
    } catch {
      // Fallback: re-run the query (backend will return cached result)
      setCurrentView(mode === "deep_dive" ? "deep_dive" : "explore");
      setQueryResult(null);
      submit(report.query, mode);
    }
  }, [submit]);

  /**
   * Handle "Deep Dive" from Explore sidebar.
   * Triggers a new deep_dive query for the selected company.
   */
  const handleDeepDive = useCallback(
    (company) => {
      const companyName = company?.name || company?.query || "";
      if (!companyName) return;
      setCurrentView("deep_dive");
      setQueryResult(null);
      submit(companyName, "deep_dive");
    },
    [submit]
  );

  /**
   * Handle PDF export for deep dive reports.
   */
  const handleDownloadPdf = useCallback(() => {
    // The PDFExport component handles the actual export
    // This callback is used by DeepDiveView's built-in button
    if (!reportRef.current) return;
    // We trigger PDF export programmatically via the PDFExport component
  }, []);

  // Extract company name and date for PDF
  const companyName =
    queryResult?.report?.company?.name ||
    queryResult?.company_name ||
    queryResult?.query ||
    "";
  const reportDate = queryResult?.cached_at
    ? new Date(queryResult.cached_at).toLocaleDateString()
    : new Date().toLocaleDateString();

  return (
    <div className="h-screen bg-[hsl(var(--background))] flex flex-col overflow-hidden">
      {/* Fixed progress bar at very top */}
      <ProgressBar currentStep={currentStep} isActive={isLoading} />

      {/* Top bar with search */}
      <TopBar
        onSubmit={handleSubmit}
        isLoading={isLoading}
        onLogoClick={handleLogoClick}
      />

      {/* Step indicator — visible during loading */}
      {isLoading && <StepIndicator currentStep={currentStep} />}

      {/* Error banner */}
      {error && (
        <div className="px-4 py-2 bg-[hsl(0,84%,60%)]/10 border-b border-[hsl(0,84%,60%)]/20">
          <p className="text-sm text-[hsl(0,84%,60%)] text-center">
            {error}
          </p>
        </div>
      )}

      {/* Main content area */}
      <main className="flex-1 overflow-hidden">
        {currentView === "history" && (
          <HistoryGrid onSelectReport={handleSelectReport} />
        )}

        {currentView === "explore" && (
          <div className="h-full">
            {isLoading && !queryResult ? (
              <div className="flex items-center justify-center h-64">
                <p className="text-sm text-[hsl(var(--muted-foreground))]">
                  Running explore query...
                </p>
              </div>
            ) : queryResult ? (
              <ExploreView data={queryResult} onDeepDive={handleDeepDive} />
            ) : null}
          </div>
        )}

        {currentView === "deep_dive" && (
          <div className="h-full" ref={reportRef}>
            {isLoading && !queryResult ? (
              <div className="flex items-center justify-center h-64">
                <p className="text-sm text-[hsl(var(--muted-foreground))]">
                  Generating deep dive report...
                </p>
              </div>
            ) : queryResult ? (
              <DeepDiveView
                data={queryResult}
                onDownloadPdf={handleDownloadPdf}
              />
            ) : null}
          </div>
        )}
      </main>

      {/* Agent log — fixed bottom, collapsible */}
      <AgentLog
        events={events}
        isActive={isLoading}
        isOpen={agentLogOpen}
        onToggle={() => setAgentLogOpen((prev) => !prev)}
      />
    </div>
  );
}

export default App;
