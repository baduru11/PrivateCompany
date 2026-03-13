import { useState, useEffect, useMemo } from "react";
import { Search, FileText, Sparkles, TrendingUp, Clock } from "lucide-react";
import { Input } from "../ui/input";
import { fetchHistory, deleteReport } from "../../lib/api";
import { cn } from "../../lib/utils";
import HistoryCard from "./HistoryCard";

/**
 * Skeleton card for loading state.
 */
function SkeletonCard({ delay = 0 }) {
  return (
    <div
      className="rounded-xl border border-[hsl(var(--border))] p-5 space-y-3 animate-init animate-fade-in-up"
      style={{ animationDelay: `${delay}s` }}
    >
      <div className="flex items-center justify-between">
        <div className="skeleton h-5 w-16 rounded-full" />
        <div className="skeleton h-4 w-4 rounded" />
      </div>
      <div className="skeleton h-5 w-3/4" />
      <div className="skeleton h-4 w-1/2" />
    </div>
  );
}

export default function HistoryGrid({ onSelectReport }) {
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");

  const handleDelete = (filename) => {
    deleteReport(filename)
      .then(() => setReports((prev) => prev.filter((r) => r.filename !== filename)))
      .catch((err) => console.warn("Could not delete report:", err.message));
  };

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchHistory()
      .then((data) => {
        if (!cancelled) {
          const list = Array.isArray(data) ? data : data.reports || data.results || [];
          setReports(list);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          console.warn("Could not fetch history:", err.message);
          setReports([]);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const filteredReports = useMemo(() => {
    if (!search.trim()) return reports;
    const q = search.toLowerCase();
    return reports.filter(
      (r) =>
        (r.query || "").toLowerCase().includes(q) ||
        (r.mode || "").toLowerCase().includes(q)
    );
  }, [reports, search]);

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-6xl mx-auto px-4 py-8 space-y-8">
        {/* Hero section */}
        <div className="relative overflow-hidden rounded-2xl border border-[hsl(var(--border))] bg-gradient-to-br from-[hsl(var(--card))] to-[hsl(var(--muted))] p-8 animate-fade-in-up">
          {/* Background decoration */}
          <div className="absolute inset-0 bg-grid opacity-30 pointer-events-none" />
          <div className="absolute top-0 right-0 w-64 h-64 bg-blue-500/5 rounded-full blur-3xl pointer-events-none" />

          <div className="relative space-y-3">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-lg bg-blue-500/10">
                <Sparkles className="w-5 h-5 text-blue-400" />
              </div>
              <h1 className="text-2xl font-bold text-[hsl(var(--foreground))]">
                CompanyIntel
              </h1>
            </div>
            <p className="text-[hsl(var(--muted-foreground))] max-w-lg leading-relaxed">
              AI-powered competitive intelligence. Explore market landscapes or deep dive into any company with real-time data analysis.
            </p>
            <div className="flex items-center gap-6 pt-2">
              <div className="flex items-center gap-2 text-sm text-[hsl(var(--muted-foreground))]">
                <TrendingUp className="w-4 h-4 text-emerald-400" />
                <span><strong className="text-[hsl(var(--foreground))]">{reports.length}</strong> reports</span>
              </div>
              <div className="flex items-center gap-2 text-sm text-[hsl(var(--muted-foreground))]">
                <Clock className="w-4 h-4 text-blue-400" />
                <span>Real-time analysis</span>
              </div>
            </div>
          </div>
        </div>

        {/* Reports header + search */}
        <div className="flex items-center justify-between gap-4">
          <h2 className="text-lg font-semibold text-[hsl(var(--foreground))]">
            Recent Reports
          </h2>
          {reports.length > 0 && (
            <div className="relative w-full max-w-xs">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[hsl(var(--muted-foreground))]" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Filter reports..."
                className="pl-9 h-9 text-sm bg-[hsl(var(--background))] border-[hsl(var(--border))] rounded-lg"
              />
            </div>
          )}
        </div>

        {/* Loading state */}
        {loading && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {[...Array(6)].map((_, i) => (
              <SkeletonCard key={i} delay={i * 0.08} />
            ))}
          </div>
        )}

        {/* Grid or empty state */}
        {!loading && filteredReports.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredReports.map((report, i) => (
              <div
                key={report.id || report.cached_at || i}
                className="animate-init animate-fade-in-up"
                style={{ animationDelay: `${i * 0.06}s` }}
              >
                <HistoryCard
                  report={report}
                  onSelect={onSelectReport}
                  onDelete={handleDelete}
                />
              </div>
            ))}
          </div>
        )}

        {!loading && filteredReports.length === 0 && (
          <div className="flex flex-col items-center justify-center py-20 text-center animate-fade-in">
            <div className="rounded-2xl bg-[hsl(var(--muted))] p-5 mb-5">
              <FileText className="h-10 w-10 text-[hsl(var(--muted-foreground))]/50" />
            </div>
            <p className="text-sm font-medium text-[hsl(var(--foreground))] mb-1">
              {reports.length === 0 ? "No reports yet" : "No matches found"}
            </p>
            <p className="text-sm text-[hsl(var(--muted-foreground))] max-w-xs">
              {reports.length === 0
                ? "Start by running a query in the search bar above."
                : "Try a different search term."}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
