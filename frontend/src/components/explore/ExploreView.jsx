import { useState, useMemo, useCallback } from "react";
import {
  LayoutGrid,
  Network,
  TrendingUp,
  Building2,
  DollarSign,
  BarChart3,
  ChevronDown,
  ChevronUp,
  ArrowRight,
} from "lucide-react";
import ForceGraph from "./ForceGraph";
import CompanySidebar from "./CompanySidebar";
import FilterChips from "./FilterChips";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { cn } from "../../lib/utils";

function matchesStage(company, stages) {
  if (stages.length === 0) return true;
  const stage = (company.funding_stage || company.stage || "").toLowerCase();
  return stages.some((s) => {
    const sl = s.toLowerCase();
    if (sl === "seed") return stage.includes("seed");
    if (sl === "a") return stage.includes("series a") || stage === "a";
    if (sl === "b") return stage.includes("series b") || stage === "b";
    if (sl === "c+") {
      return /series [c-z]/i.test(stage) || /^[c-z]$/i.test(stage) || stage.includes("ipo") || stage.includes("late");
    }
    return false;
  });
}

function matchesYear(company, years) {
  if (years.length === 0) return true;
  const yr = Number(company.founding_year || company.founded);
  if (!yr) return years.length === 0;
  return years.some((range) => {
    if (range === "2020+") return yr >= 2020;
    if (range === "2015-19") return yr >= 2015 && yr <= 2019;
    if (range === "2010-14") return yr >= 2010 && yr <= 2014;
    if (range === "Pre-2010") return yr < 2010;
    return false;
  });
}

function formatFunding(num) {
  if (!num || num === 0) return "N/A";
  if (num >= 1e9) return `$${(num / 1e9).toFixed(1)}B`;
  if (num >= 1e6) return `$${(num / 1e6).toFixed(1)}M`;
  if (num >= 1e3) return `$${(num / 1e3).toFixed(0)}K`;
  return `$${num}`;
}

function confidenceColor(c) {
  if (c == null) return "text-zinc-500";
  if (c >= 0.7) return "text-emerald-400";
  if (c >= 0.4) return "text-amber-400";
  return "text-red-400";
}

/**
 * Stat card with gradient icon background.
 */
function StatCard({ icon: Icon, label, value, color = "blue" }) {
  const colorMap = {
    blue: "from-blue-500/15 to-blue-600/5 text-blue-400",
    green: "from-emerald-500/15 to-emerald-600/5 text-emerald-400",
    purple: "from-purple-500/15 to-purple-600/5 text-purple-400",
    amber: "from-amber-500/15 to-amber-600/5 text-amber-400",
  };

  return (
    <div className="flex items-center gap-3 px-4 py-3.5 rounded-xl bg-[hsl(var(--card))] border border-[hsl(var(--border))] hover-glow transition-all">
      <div className={cn("p-2.5 rounded-lg bg-gradient-to-br", colorMap[color])}>
        <Icon className="w-4 h-4" />
      </div>
      <div className="min-w-0">
        <p className="text-lg font-bold text-[hsl(var(--foreground))] leading-tight tabular-nums">{value}</p>
        <p className="text-[11px] text-[hsl(var(--muted-foreground))] truncate">{label}</p>
      </div>
    </div>
  );
}

/**
 * Company row in the table view.
 */
function CompanyRow({ company, index, onSelect, onDeepDive }) {
  return (
    <tr
      role="button"
      tabIndex={0}
      onClick={() => onSelect(company)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect(company);
        }
      }}
      className="group cursor-pointer border-b border-[hsl(var(--border))]/40 hover:bg-[hsl(var(--accent))]/50 transition-colors focus-visible:outline-none focus-visible:bg-[hsl(var(--accent))]/50"
    >
      <td className="py-3.5 px-4 text-sm">
        <div className="flex items-center gap-2.5">
          <span className="text-[10px] text-[hsl(var(--muted-foreground))]/50 font-mono w-5 tabular-nums">{index + 1}</span>
          <span className="font-medium text-[hsl(var(--foreground))] group-hover:text-[hsl(var(--primary))] transition-colors">{company.name}</span>
        </div>
      </td>
      <td className="py-3.5 px-3">
        <Badge variant="outline" className="text-[10px] font-normal">
          {company.sub_sector || "\u2014"}
        </Badge>
      </td>
      <td className="py-3.5 px-3 text-sm font-mono text-[hsl(var(--foreground))] tabular-nums">
        {company.funding || formatFunding(company.funding_numeric)}
      </td>
      <td className="py-3.5 px-3 text-sm text-[hsl(var(--muted-foreground))]">
        {company.funding_stage || "\u2014"}
      </td>
      <td className="py-3.5 px-3 text-sm text-[hsl(var(--muted-foreground))] tabular-nums">
        {company.founding_year || "\u2014"}
      </td>
      <td className="py-3.5 px-3 text-sm text-[hsl(var(--muted-foreground))]">
        {company.headquarters || "\u2014"}
      </td>
      <td className="py-3.5 px-3">
        <div className={cn("text-xs font-mono tabular-nums", confidenceColor(company.confidence))}>
          {company.confidence != null ? `${Math.round(company.confidence * 100)}%` : "\u2014"}
        </div>
      </td>
      <td className="py-3.5 px-3">
        <Button
          size="sm"
          variant="ghost"
          className="opacity-0 group-hover:opacity-100 transition-opacity h-7 text-xs cursor-pointer"
          onClick={(e) => {
            e.stopPropagation();
            onDeepDive(company);
          }}
        >
          Deep Dive <ArrowRight className="w-3 h-3 ml-1" />
        </Button>
      </td>
    </tr>
  );
}

export default function ExploreView({ data, onDeepDive }) {
  const [selectedCompany, setSelectedCompany] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [viewMode, setViewMode] = useState("graph");
  const [summaryExpanded, setSummaryExpanded] = useState(true);
  const [activeFilters, setActiveFilters] = useState({
    subSectors: [],
    stages: [],
    years: [],
  });
  const [tableSortKey, setTableSortKey] = useState("funding_numeric");
  const [tableSortDir, setTableSortDir] = useState("desc");

  const allCompanies = useMemo(() => {
    if (!data) return [];
    const companies = data.report?.companies || data.companies || data.result?.companies || [];
    return companies.map((c, i) => ({
      id: c.id || c.name || `company-${i}`,
      name: c.name || "Unknown",
      sub_sector: c.sub_sector || c.sector || "",
      funding_numeric: c.funding_numeric || 0,
      funding: c.funding || c.funding_total || c.funding_amount || "",
      funding_stage: c.funding_stage || c.stage || "",
      founding_year: c.founding_year || c.founded || "",
      description: c.description || "",
      confidence: c.confidence ?? null,
      headquarters: c.headquarters || c.hq || "",
      key_investors: c.key_investors || [],
    }));
  }, [data]);

  const subSectors = useMemo(() => {
    const set = new Set(allCompanies.map((c) => c.sub_sector).filter(Boolean));
    return [...set].sort();
  }, [allCompanies]);

  const filteredCompanies = useMemo(() => {
    return allCompanies.filter((c) => {
      if (activeFilters.subSectors.length > 0 && !activeFilters.subSectors.includes(c.sub_sector)) return false;
      if (!matchesStage(c, activeFilters.stages)) return false;
      if (!matchesYear(c, activeFilters.years)) return false;
      return true;
    });
  }, [allCompanies, activeFilters]);

  const sortedCompanies = useMemo(() => {
    return [...filteredCompanies].sort((a, b) => {
      let av = a[tableSortKey];
      let bv = b[tableSortKey];
      if (typeof av === "string") av = av.toLowerCase();
      if (typeof bv === "string") bv = bv.toLowerCase();
      if (av < bv) return tableSortDir === "asc" ? -1 : 1;
      if (av > bv) return tableSortDir === "asc" ? 1 : -1;
      return 0;
    });
  }, [filteredCompanies, tableSortKey, tableSortDir]);

  const stats = useMemo(() => {
    const totalFunding = filteredCompanies.reduce((sum, c) => sum + (c.funding_numeric || 0), 0);
    const avgConfidence = filteredCompanies.length > 0
      ? filteredCompanies.reduce((sum, c) => sum + (c.confidence || 0), 0) / filteredCompanies.length
      : 0;
    const sectorCounts = {};
    filteredCompanies.forEach((c) => {
      const s = c.sub_sector || "Unknown";
      sectorCounts[s] = (sectorCounts[s] || 0) + 1;
    });
    return { totalFunding, avgConfidence, sectorCounts };
  }, [filteredCompanies]);

  const sectorName = data?.report?.sector || data?.sector || data?.report?.query || data?.query || "Market Landscape";
  const summary = data?.report?.summary || data?.summary || "";

  const handleNodeClick = useCallback((node) => {
    setSelectedCompany(node);
    setSidebarOpen(true);
  }, []);

  const handleCloseSidebar = useCallback(() => {
    setSidebarOpen(false);
    setSelectedCompany(null);
  }, []);

  const handleDeepDive = useCallback(
    (company) => { onDeepDive?.(company); },
    [onDeepDive]
  );

  const handleSort = (key) => {
    if (tableSortKey === key) {
      setTableSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setTableSortKey(key);
      setTableSortDir("desc");
    }
  };

  const SortHeader = ({ label, sortKey }) => (
    <th
      onClick={() => handleSort(sortKey)}
      className="py-3 px-3 text-[10px] font-semibold uppercase tracking-wider text-[hsl(var(--muted-foreground))] cursor-pointer hover:text-[hsl(var(--foreground))] transition-colors text-left select-none"
    >
      <span className="flex items-center gap-1">
        {label}
        {tableSortKey === sortKey && (
          tableSortDir === "asc" ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />
        )}
      </span>
    </th>
  );

  return (
    <div className="flex flex-col h-full w-full overflow-hidden">
      {/* Header bar */}
      <div className="flex items-center justify-between px-5 py-3 glass border-b border-[hsl(var(--border))]">
        <div className="flex items-center gap-3">
          <h2 className="text-base font-bold text-[hsl(var(--foreground))]">
            {sectorName}
          </h2>
          <Badge variant="outline" className="text-[10px] font-mono tabular-nums">
            {filteredCompanies.length} compan{filteredCompanies.length === 1 ? "y" : "ies"}
            {filteredCompanies.length !== allCompanies.length && ` / ${allCompanies.length}`}
          </Badge>
        </div>
        <div className="flex items-center gap-1 bg-[hsl(var(--muted))] p-1 rounded-lg">
          <button
            onClick={() => setViewMode("graph")}
            className={cn(
              "p-2 rounded-md transition-all cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--ring))]",
              viewMode === "graph"
                ? "bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] shadow-sm"
                : "text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]"
            )}
            title="Graph view"
          >
            <Network className="w-4 h-4" />
          </button>
          <button
            onClick={() => setViewMode("table")}
            className={cn(
              "p-2 rounded-md transition-all cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--ring))]",
              viewMode === "table"
                ? "bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] shadow-sm"
                : "text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]"
            )}
            title="Table view"
          >
            <LayoutGrid className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Stats + summary panel */}
      <div className="border-b border-[hsl(var(--border))] bg-[hsl(var(--card))]/50">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 px-5 py-3.5">
          <StatCard icon={Building2} label="Companies" value={filteredCompanies.length} color="blue" />
          <StatCard icon={DollarSign} label="Total Funding" value={formatFunding(stats.totalFunding)} color="green" />
          <StatCard icon={BarChart3} label="Sub-Sectors" value={Object.keys(stats.sectorCounts).length} color="purple" />
          <StatCard icon={TrendingUp} label="Avg Confidence" value={`${Math.round(stats.avgConfidence * 100)}%`} color="amber" />
        </div>

        {summary && (
          <div className="px-5 pb-3.5">
            <button
              onClick={() => setSummaryExpanded((v) => !v)}
              className="flex items-center gap-1.5 text-[11px] font-semibold text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] transition-colors mb-1.5 cursor-pointer"
            >
              {summaryExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
              AI Summary
            </button>
            {summaryExpanded && (
              <p className="text-sm text-[hsl(var(--foreground))]/80 leading-relaxed pl-4 border-l-2 border-blue-500/30 animate-fade-in">
                {summary}
              </p>
            )}
          </div>
        )}
      </div>

      {/* Filter chips */}
      <FilterChips
        subSectors={subSectors}
        activeFilters={activeFilters}
        onFilterChange={setActiveFilters}
      />

      {/* Main content area */}
      <div className="flex flex-1 min-h-0 relative overflow-hidden">
        {viewMode === "graph" ? (
          <>
            <div
              className="flex-1 h-full min-h-0 transition-all duration-300"
              style={{ marginRight: sidebarOpen ? "320px" : "0" }}
            >
              <ForceGraph
                companies={filteredCompanies}
                onNodeClick={handleNodeClick}
                selectedNode={selectedCompany?.id || selectedCompany?.name}
              />
            </div>
            <CompanySidebar
              company={selectedCompany}
              isOpen={sidebarOpen}
              onClose={handleCloseSidebar}
              onDeepDive={handleDeepDive}
            />
          </>
        ) : (
          <div className="flex-1 overflow-auto">
            <table className="w-full">
              <thead className="sticky top-0 glass-strong border-b border-[hsl(var(--border))] z-10">
                <tr>
                  <SortHeader label="Company" sortKey="name" />
                  <SortHeader label="Sector" sortKey="sub_sector" />
                  <SortHeader label="Funding" sortKey="funding_numeric" />
                  <SortHeader label="Stage" sortKey="funding_stage" />
                  <SortHeader label="Founded" sortKey="founding_year" />
                  <SortHeader label="HQ" sortKey="headquarters" />
                  <SortHeader label="Confidence" sortKey="confidence" />
                  <th className="py-3 px-3 w-24"></th>
                </tr>
              </thead>
              <tbody>
                {sortedCompanies.map((c, i) => (
                  <CompanyRow
                    key={c.id}
                    company={c}
                    index={i}
                    onSelect={(company) => {
                      setSelectedCompany(company);
                      setSidebarOpen(true);
                    }}
                    onDeepDive={handleDeepDive}
                  />
                ))}
              </tbody>
            </table>
            {sortedCompanies.length === 0 && (
              <div className="flex items-center justify-center h-40 text-sm text-[hsl(var(--muted-foreground))]">
                No companies match the current filters.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
