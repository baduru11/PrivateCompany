import { useMemo, useCallback } from "react";
import {
  Building2,
  Calendar,
  MapPin,
  Users,
  Layers,
  Download,
  User,
} from "lucide-react";
import { Button } from "../ui/button";
import SectionNav from "./SectionNav";
import ReportSection from "./ReportSection";
import FundingChart from "./FundingChart";
import NewsCard from "./NewsCard";
import CompetitorTable from "./CompetitorTable";
import RedFlagCard from "./RedFlagCard";

/**
 * Section IDs used for scroll anchors and navigation.
 */
const SECTION_IDS = {
  overview: "section-overview",
  funding: "section-funding",
  people: "section-people",
  product: "section-product",
  news: "section-news",
  competitors: "section-competitors",
  redFlags: "section-red-flags",
};

/**
 * Extract per-section confidence from critic report if available.
 * Falls back to the main report confidence.
 */
function getSectionConfidence(data, sectionKey) {
  // Try critic per-section scores first
  const critic = data?.critic || data?.critic_report;
  if (critic?.section_scores?.[sectionKey] != null) {
    return critic.section_scores[sectionKey];
  }
  // Fall back to overall confidence
  return data?.confidence ?? data?.report?.confidence ?? null;
}

/**
 * Extract source URLs for a given section from the data.
 */
function getSectionSources(data, sectionKey) {
  const sources = data?.sources || data?.report?.sources || {};
  const sectionSources = sources[sectionKey] || [];
  return sectionSources.map((s) =>
    typeof s === "string" ? { url: s } : s
  );
}

/**
 * Main Deep Dive layout composing SectionNav + all ReportSections.
 *
 * Props:
 *  - data: Combined DeepDiveReport + CriticReport object from the API
 *  - onDownloadPdf: optional callback for PDF export
 */
export default function DeepDiveView({ data, onDownloadPdf }) {
  const report = data?.report || data || {};
  const critic = data?.critic || data?.critic_report || {};

  // Company info (try multiple shapes)
  const company = report.company || report.overview || {};
  const companyName = company.name || report.company_name || report.name || "Company";

  // Build nav sections with confidence
  const navSections = useMemo(() => {
    return [
      { id: SECTION_IDS.overview, title: "Overview", confidence: getSectionConfidence(data, "overview") },
      { id: SECTION_IDS.funding, title: "Funding", confidence: getSectionConfidence(data, "funding") },
      { id: SECTION_IDS.people, title: "Key People", confidence: getSectionConfidence(data, "people") },
      { id: SECTION_IDS.product, title: "Product / Tech", confidence: getSectionConfidence(data, "product") },
      { id: SECTION_IDS.news, title: "Recent News", confidence: getSectionConfidence(data, "news") },
      { id: SECTION_IDS.competitors, title: "Competitors", confidence: getSectionConfidence(data, "competitors") },
      { id: SECTION_IDS.redFlags, title: "Red Flags", confidence: getSectionConfidence(data, "red_flags") },
    ];
  }, [data]);

  const handlePdf = useCallback(() => {
    onDownloadPdf?.();
  }, [onDownloadPdf]);

  // Data extraction helpers
  const description = company.description || report.description || "";
  const metrics = [
    { label: "Founded", value: company.founded || company.founding_year || report.founded || "—", icon: Calendar },
    { label: "HQ", value: company.headquarters || company.hq || report.headquarters || "—", icon: MapPin },
    { label: "Headcount", value: company.headcount || company.employees || report.headcount || "—", icon: Users },
    { label: "Stage", value: company.stage || company.funding_stage || report.stage || "—", icon: Layers },
  ];

  const fundingRounds = report.funding_rounds || report.funding?.rounds || [];
  const people = report.key_people || report.people || [];
  const productText = report.product || report.technology || report.product_technology || "";
  const newsItems = report.news || report.recent_news || [];
  const competitors = report.competitors || [];
  const redFlags = critic.red_flags || report.red_flags || [];

  return (
    <div className="flex h-full w-full overflow-hidden">
      {/* Sidebar nav */}
      <div className="hidden md:block border-r border-[hsl(var(--border))] overflow-y-auto">
        <SectionNav sections={navSections} />
      </div>

      {/* Main scrollable content */}
      <div className="flex-1 overflow-y-auto">
        {/* Top bar with company name and PDF button */}
        <div className="sticky top-0 z-10 flex items-center justify-between px-6 py-3 bg-[hsl(var(--background))]/95 backdrop-blur-sm border-b border-[hsl(var(--border))]">
          <h1 className="text-xl font-bold text-[hsl(var(--foreground))] truncate">
            {companyName}
          </h1>
          {onDownloadPdf && (
            <Button variant="outline" size="sm" onClick={handlePdf}>
              <Download className="h-4 w-4 mr-2" />
              Export PDF
            </Button>
          )}
        </div>

        <div className="p-6 space-y-6 max-w-4xl">
          {/* 1. Overview */}
          <ReportSection
            id={SECTION_IDS.overview}
            title="Overview"
            confidence={getSectionConfidence(data, "overview")}
            sourceCount={getSectionSources(data, "overview").length}
            sourceUrls={getSectionSources(data, "overview")}
          >
            {description && (
              <p className="text-sm text-[hsl(var(--muted-foreground))] leading-relaxed mb-4">
                {description}
              </p>
            )}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              {metrics.map((m) => {
                const Icon = m.icon;
                return (
                  <div
                    key={m.label}
                    className="rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--muted))]/30 p-3 space-y-1"
                  >
                    <div className="flex items-center gap-1.5 text-[hsl(var(--muted-foreground))]">
                      <Icon className="h-3.5 w-3.5" />
                      <span className="text-xs">{m.label}</span>
                    </div>
                    <p className="text-sm font-medium text-[hsl(var(--foreground))]">
                      {m.value}
                    </p>
                  </div>
                );
              })}
            </div>
          </ReportSection>

          {/* 2. Funding */}
          <ReportSection
            id={SECTION_IDS.funding}
            title="Funding"
            confidence={getSectionConfidence(data, "funding")}
            sourceCount={getSectionSources(data, "funding").length}
            sourceUrls={getSectionSources(data, "funding")}
          >
            <FundingChart fundingRounds={fundingRounds} />
          </ReportSection>

          {/* 3. Key People */}
          <ReportSection
            id={SECTION_IDS.people}
            title="Key People"
            confidence={getSectionConfidence(data, "people")}
            sourceCount={getSectionSources(data, "people").length}
            sourceUrls={getSectionSources(data, "people")}
          >
            {people.length > 0 ? (
              <div className="grid gap-3 sm:grid-cols-2">
                {people.map((person, i) => (
                  <div
                    key={person.name || i}
                    className="flex items-start gap-3 rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--muted))]/20 p-3"
                  >
                    <div className="rounded-full bg-[hsl(var(--muted))] p-2">
                      <User className="h-4 w-4 text-[hsl(var(--muted-foreground))]" />
                    </div>
                    <div className="flex-1 min-w-0 space-y-0.5">
                      <p className="text-sm font-medium text-[hsl(var(--foreground))] truncate">
                        {person.name || "Unknown"}
                      </p>
                      {(person.title || person.role) && (
                        <p className="text-xs text-[hsl(var(--muted-foreground))]">
                          {person.title || person.role}
                        </p>
                      )}
                      {person.background && (
                        <p className="text-xs text-[hsl(var(--muted-foreground))] leading-relaxed mt-1">
                          {person.background}
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-[hsl(var(--muted-foreground))] italic">
                No key people data available.
              </p>
            )}
          </ReportSection>

          {/* 4. Product / Technology */}
          <ReportSection
            id={SECTION_IDS.product}
            title="Product / Technology"
            confidence={getSectionConfidence(data, "product")}
            sourceCount={getSectionSources(data, "product").length}
            sourceUrls={getSectionSources(data, "product")}
          >
            {productText ? (
              <div className="text-sm text-[hsl(var(--muted-foreground))] leading-relaxed whitespace-pre-line">
                {productText}
              </div>
            ) : (
              <p className="text-sm text-[hsl(var(--muted-foreground))] italic">
                No product/technology data available.
              </p>
            )}
          </ReportSection>

          {/* 5. Recent News */}
          <ReportSection
            id={SECTION_IDS.news}
            title="Recent News"
            confidence={getSectionConfidence(data, "news")}
            sourceCount={getSectionSources(data, "news").length}
            sourceUrls={getSectionSources(data, "news")}
          >
            {newsItems.length > 0 ? (
              <div className="space-y-3">
                {newsItems.map((item, i) => (
                  <NewsCard key={item.title || i} newsItem={item} />
                ))}
              </div>
            ) : (
              <p className="text-sm text-[hsl(var(--muted-foreground))] italic">
                No recent news available.
              </p>
            )}
          </ReportSection>

          {/* 6. Competitors */}
          <ReportSection
            id={SECTION_IDS.competitors}
            title="Competitors"
            confidence={getSectionConfidence(data, "competitors")}
            sourceCount={getSectionSources(data, "competitors").length}
            sourceUrls={getSectionSources(data, "competitors")}
          >
            <CompetitorTable competitors={competitors} />
          </ReportSection>

          {/* 7. Red Flags */}
          <ReportSection
            id={SECTION_IDS.redFlags}
            title="Red Flags"
            confidence={getSectionConfidence(data, "red_flags")}
            sourceCount={getSectionSources(data, "red_flags").length}
            sourceUrls={getSectionSources(data, "red_flags")}
          >
            {redFlags.length > 0 ? (
              <div className="space-y-3">
                {redFlags.map((flag, i) => {
                  const flagText = typeof flag === "string" ? flag : flag.content || flag.text || "";
                  const flagConf = typeof flag === "object" ? flag.confidence : undefined;
                  const flagSources = typeof flag === "object" ? (flag.sources || flag.source_urls || []) : [];
                  return (
                    <RedFlagCard
                      key={i}
                      content={flagText}
                      confidence={flagConf}
                      sourceUrls={flagSources.map((s) =>
                        typeof s === "string" ? { url: s } : s
                      )}
                    />
                  );
                })}
              </div>
            ) : (
              <p className="text-sm text-emerald-400/80 italic">
                No red flags identified.
              </p>
            )}
          </ReportSection>
        </div>
      </div>
    </div>
  );
}
