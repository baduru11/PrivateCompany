import { useMemo, useCallback } from "react";
import {
  Building2,
  Calendar,
  MapPin,
  Users,
  Layers,
  Download,
  User,
  AlertTriangle,
  ExternalLink,
  TrendingUp,
  DollarSign,
  Shield,
  Target,
  BarChart3,
} from "lucide-react";
import { Button } from "../ui/button";
import SectionNav from "./SectionNav";
import ReportSection from "./ReportSection";
import FundingChart from "./FundingChart";
import NewsCard from "./NewsCard";
import CompetitorTable from "./CompetitorTable";
import RedFlagCard from "./RedFlagCard";
import MarkdownProse from "../shared/MarkdownProse";

const SECTION_IDS = {
  overview: "section-overview",
  funding: "section-funding",
  people: "section-people",
  product: "section-product",
  market: "section-market",
  businessModel: "section-business-model",
  competitiveAdvantages: "section-competitive-advantages",
  traction: "section-traction",
  news: "section-news",
  competitors: "section-competitors",
  risks: "section-risks",
  redFlags: "section-red-flags",
};

function getSectionConfidence(data, sectionKey) {
  const critic = data?.critic || data?.critic_report;
  const keyMap = {
    people: 'key_people',
    product: 'product_technology',
    news: 'recent_news',
    market: 'market_opportunity',
    businessModel: 'business_model',
    competitiveAdvantages: 'competitive_advantages',
  };
  const criticKey = keyMap[sectionKey] || sectionKey;
  if (critic?.section_scores?.[criticKey] != null) {
    return critic.section_scores[criticKey];
  }
  const report = data?.report || data || {};
  const fieldMap = {
    overview: 'overview',
    funding: 'funding',
    people: 'key_people',
    product: 'product_technology',
    news: 'recent_news',
    competitors: 'competitors',
    red_flags: 'red_flags',
    market: 'market_opportunity',
    businessModel: 'business_model',
    competitiveAdvantages: 'competitive_advantages',
    traction: 'traction',
    risks: 'risks',
  };
  const field = fieldMap[sectionKey];
  if (field && report[field]?.confidence != null) {
    return report[field].confidence;
  }
  return data?.confidence ?? data?.report?.confidence ?? null;
}

function getSectionSources(data, sectionKey) {
  const report = data?.report || data || {};
  const fieldMap = {
    overview: 'overview',
    funding: 'funding',
    people: 'key_people',
    product: 'product_technology',
    news: 'recent_news',
    competitors: 'competitors',
    red_flags: 'red_flags',
    market: 'market_opportunity',
    businessModel: 'business_model',
    competitiveAdvantages: 'competitive_advantages',
    traction: 'traction',
    risks: 'risks',
  };
  const field = fieldMap[sectionKey];
  const section = field ? report[field] : null;
  if (section?.source_urls?.length) {
    return section.source_urls.map((s) => typeof s === "string" ? { url: s } : s);
  }
  const sources = data?.sources || data?.report?.sources || {};
  const sectionSources = sources[sectionKey] || [];
  return sectionSources.map((s) =>
    typeof s === "string" ? { url: s } : s
  );
}

/**
 * Metric card for the overview section.
 */
function MetricCard({ icon: Icon, label, value, color = "blue" }) {
  const colorMap = {
    blue: "from-blue-500/12 to-blue-600/5 text-blue-400",
    green: "from-emerald-500/12 to-emerald-600/5 text-emerald-400",
    purple: "from-purple-500/12 to-purple-600/5 text-purple-400",
    amber: "from-amber-500/12 to-amber-600/5 text-amber-400",
  };
  return (
    <div className="rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-4 space-y-2 hover-glow transition-all">
      <div className={`inline-flex p-2 rounded-lg bg-gradient-to-br ${colorMap[color]}`}>
        <Icon className="h-4 w-4" />
      </div>
      <div>
        <p className="text-xs text-[hsl(var(--muted-foreground))]">{label}</p>
        <p className="text-sm font-semibold text-[hsl(var(--foreground))] mt-0.5">
          {value}
        </p>
      </div>
    </div>
  );
}

/** LinkedIn icon (inline SVG for brand accuracy). */
function LinkedInIcon({ className }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className}>
      <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
    </svg>
  );
}

/** Crunchbase icon (inline SVG). */
function CrunchbaseIcon({ className }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className}>
      <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.394 17.505c-.707.707-1.553 1.262-2.51 1.65a7.802 7.802 0 01-3.084.615 7.766 7.766 0 01-3.077-.615 7.931 7.931 0 01-2.51-1.65 7.84 7.84 0 01-1.693-2.51A7.694 7.694 0 013.9 12a7.76 7.76 0 01.62-3.077 8.04 8.04 0 011.693-2.51A7.84 7.84 0 018.723 4.72a7.76 7.76 0 013.077-.62c1.08 0 2.112.208 3.084.615a7.932 7.932 0 012.51 1.693 7.84 7.84 0 011.693 2.51c.407.972.615 2.004.615 3.082a7.694 7.694 0 01-.615 2.995 8.04 8.04 0 01-1.693 2.51z" />
    </svg>
  );
}

export default function DeepDiveView({ data, onDownloadPdf }) {
  const report = data?.report || data || {};
  const critic = data?.critic || data?.critic_report || {};

  const overviewSection = report.overview || {};
  const isOverviewSection = typeof overviewSection === "object" && overviewSection.content;
  const company = isOverviewSection ? {} : (report.company || overviewSection);
  const companyName = report.company_name || company.name || report.name || "Company";

  // Due diligence sections availability
  const hasMarket = report.market_opportunity?.content;
  const hasBusinessModel = report.business_model?.content;
  const hasCompetitiveAdvantages = report.competitive_advantages?.content;
  const hasTraction = report.traction?.content;
  const hasRisks = report.risks?.content || (report.risk_entries?.length > 0);

  const navSections = useMemo(() => {
    const sections = [
      { id: SECTION_IDS.overview, title: "Overview", confidence: getSectionConfidence(data, "overview") },
      { id: SECTION_IDS.funding, title: "Funding", confidence: getSectionConfidence(data, "funding") },
      { id: SECTION_IDS.people, title: "Key People", confidence: getSectionConfidence(data, "people") },
      { id: SECTION_IDS.product, title: "Product / Tech", confidence: getSectionConfidence(data, "product") },
    ];
    if (hasMarket) sections.push({ id: SECTION_IDS.market, title: "Market Opportunity", confidence: getSectionConfidence(data, "market") });
    if (hasBusinessModel) sections.push({ id: SECTION_IDS.businessModel, title: "Business Model", confidence: getSectionConfidence(data, "businessModel") });
    if (hasCompetitiveAdvantages) sections.push({ id: SECTION_IDS.competitiveAdvantages, title: "Competitive Advantages", confidence: getSectionConfidence(data, "competitiveAdvantages") });
    if (hasTraction) sections.push({ id: SECTION_IDS.traction, title: "Traction", confidence: getSectionConfidence(data, "traction") });
    sections.push(
      { id: SECTION_IDS.news, title: "Recent News", confidence: getSectionConfidence(data, "news") },
      { id: SECTION_IDS.competitors, title: "Competitors", confidence: getSectionConfidence(data, "competitors") },
    );
    if (hasRisks) sections.push({ id: SECTION_IDS.risks, title: "Risks", confidence: getSectionConfidence(data, "risks") });
    sections.push({ id: SECTION_IDS.redFlags, title: "Red Flags", confidence: getSectionConfidence(data, "red_flags") });
    return sections;
  }, [data, hasMarket, hasBusinessModel, hasCompetitiveAdvantages, hasTraction, hasRisks]);

  const handlePdf = useCallback(() => {
    onDownloadPdf?.();
  }, [onDownloadPdf]);

  const textOf = (v) => {
    if (!v) return "";
    if (typeof v === "string") return v;
    if (typeof v === "object" && v.content) return v.content;
    return "";
  };

  const description = textOf(report.overview) || company.description || report.description || "";
  const metrics = [
    { label: "Founded", value: report.founded || company.founded || company.founding_year || "\u2014", icon: Calendar, color: "blue" },
    { label: "HQ", value: report.headquarters || company.headquarters || company.hq || "\u2014", icon: MapPin, color: "green" },
    { label: "Headcount", value: report.headcount || company.headcount || company.employees || "\u2014", icon: Users, color: "purple" },
    { label: "Stage", value: report.funding_stage || company.stage || company.funding_stage || "\u2014", icon: Layers, color: "amber" },
  ];

  const fundingRounds = report.funding_rounds || (Array.isArray(report.funding) ? report.funding : report.funding?.rounds) || [];
  const fundingText = textOf(report.funding) || "";
  const people = report.people_entries?.length ? report.people_entries : (Array.isArray(report.key_people) ? report.key_people : (Array.isArray(report.people) ? report.people : []));
  const peopleText = textOf(report.key_people) || textOf(report.people) || "";
  const productText = textOf(report.product_technology) || textOf(report.product) || textOf(report.technology) || "";
  const newsItems = (report.news_items || (Array.isArray(report.news) ? report.news : []) || (Array.isArray(report.recent_news) ? report.recent_news : []))
    .slice()
    .sort((a, b) => {
      if (!a.date && !b.date) return 0;
      if (!a.date) return 1;
      if (!b.date) return -1;
      return new Date(b.date) - new Date(a.date);
    });
  const newsText = textOf(report.recent_news) || textOf(report.news) || "";
  const competitors = report.competitor_entries || (Array.isArray(report.competitors) ? report.competitors : []);
  const competitorsText = textOf(report.competitors) || "";
  const redFlags = report.red_flag_entries?.length ? report.red_flag_entries : (Array.isArray(critic.red_flags) ? critic.red_flags : (Array.isArray(report.red_flags) ? report.red_flags : []));
  const redFlagsText = textOf(report.red_flags) || textOf(critic.red_flags) || "";
  const riskEntries = report.risk_entries || [];
  const risksText = textOf(report.risks) || "";

  const linkedinUrl = report.linkedin_url;
  const crunchbaseUrl = report.crunchbase_url;

  const severityColor = {
    low: "border-yellow-500/25 bg-yellow-500/5 text-yellow-400",
    medium: "border-amber-500/25 bg-amber-500/5 text-amber-400",
    high: "border-red-500/25 bg-red-500/5 text-red-400",
  };

  const riskCategoryIcon = {
    regulatory: Shield,
    market: TrendingUp,
    technology: Target,
    team: Users,
    financial: DollarSign,
    competitive: BarChart3,
  };

  return (
    <div className="flex h-full w-full overflow-hidden">
      {/* Sidebar nav */}
      <div className="hidden md:block border-r border-[hsl(var(--border))] overflow-y-auto">
        <SectionNav sections={navSections} />
      </div>

      {/* Main scrollable content */}
      <div className="flex-1 overflow-y-auto">
        {/* Top bar with company name, links, and PDF button */}
        <div className="sticky top-0 z-10 flex items-center justify-between px-6 py-3.5 glass-strong border-b border-[hsl(var(--border))]">
          <div className="flex items-center gap-3">
            {report.logo_url ? (
              <img
                src={report.logo_url}
                alt={`${companyName} logo`}
                className="w-9 h-9 rounded-xl border border-[hsl(var(--border))] object-contain bg-white"
                onError={(e) => {
                  if (e.target.src.includes("clearbit")) {
                    try {
                      const domain = new URL(e.target.src).pathname.slice(1);
                      e.target.src = `https://www.google.com/s2/favicons?domain=${domain}&sz=128`;
                    } catch {
                      e.target.style.display = "none";
                      e.target.nextElementSibling.style.display = "flex";
                    }
                  } else {
                    e.target.style.display = "none";
                    e.target.nextElementSibling.style.display = "flex";
                  }
                }}
              />
            ) : null}
            <div
              className="w-9 h-9 rounded-xl bg-gradient-to-br from-blue-500/15 to-blue-600/5 flex items-center justify-center border border-blue-500/20"
              style={{ display: report.logo_url ? "none" : "flex" }}
            >
              <Building2 className="w-4 h-4 text-blue-400" />
            </div>
            <h1 className="text-xl font-bold text-[hsl(var(--foreground))] truncate">
              {companyName}
            </h1>
            {/* External profile links */}
            <div className="flex items-center gap-1.5 ml-1">
              {linkedinUrl && (
                <a
                  href={linkedinUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="p-1.5 rounded-lg text-[hsl(var(--muted-foreground))] hover:text-[#0A66C2] hover:bg-[#0A66C2]/10 transition-colors cursor-pointer"
                  aria-label="View LinkedIn profile"
                  title="LinkedIn"
                >
                  <LinkedInIcon className="h-4 w-4" />
                </a>
              )}
              {crunchbaseUrl && (
                <a
                  href={crunchbaseUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="p-1.5 rounded-lg text-[hsl(var(--muted-foreground))] hover:text-[#0288D1] hover:bg-[#0288D1]/10 transition-colors cursor-pointer"
                  aria-label="View Crunchbase profile"
                  title="Crunchbase"
                >
                  <CrunchbaseIcon className="h-4 w-4" />
                </a>
              )}
            </div>
          </div>
          {onDownloadPdf && (
            <Button variant="outline" size="sm" onClick={handlePdf} className="rounded-lg cursor-pointer">
              <Download className="h-4 w-4 mr-2" />
              Export PDF
            </Button>
          )}
        </div>

        {/* Low-confidence warning banner */}
        {(() => {
          const lowConfSections = navSections.filter(
            (s) => s.confidence !== null && s.confidence < 0.4
          );
          if (lowConfSections.length === 0) return null;
          return (
            <div className="mx-6 mt-5 rounded-xl border border-amber-500/25 bg-amber-500/5 px-5 py-3.5 flex items-start gap-3 animate-fade-in">
              <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-amber-400">
                  {lowConfSections.length} section{lowConfSections.length > 1 ? "s" : ""} with low confidence
                </p>
                <p className="mt-0.5 text-xs text-amber-400/70">
                  {lowConfSections.map((s) => s.title).join(", ")} — data may be incomplete or unverified
                </p>
              </div>
            </div>
          );
        })()}

        <div className="p-6 space-y-6 max-w-5xl mx-auto">
          {/* 1. Overview */}
          <ReportSection
            id={SECTION_IDS.overview}
            title="Overview"
            confidence={getSectionConfidence(data, "overview")}
            sourceCount={report.overview?.source_count || getSectionSources(data, "overview").length}
            sourceUrls={getSectionSources(data, "overview")}
          >
            {description && (
              <div className="mb-5">
                <MarkdownProse content={description} citations={report.citations || []} />
              </div>
            )}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {metrics.map((m, i) => (
                <div
                  key={m.label}
                  className="animate-init animate-fade-in-up"
                  style={{ animationDelay: `${i * 0.08}s` }}
                >
                  <MetricCard icon={m.icon} label={m.label} value={m.value} color={m.color} />
                </div>
              ))}
            </div>
          </ReportSection>

          {/* 2. Funding */}
          <ReportSection
            id={SECTION_IDS.funding}
            title="Funding"
            confidence={getSectionConfidence(data, "funding")}
            sourceCount={report.funding?.source_count || getSectionSources(data, "funding").length}
            sourceUrls={getSectionSources(data, "funding")}
          >
            {fundingText && (
              <div className="mb-5">
                <MarkdownProse content={fundingText} citations={report.citations || []} />
              </div>
            )}
            <FundingChart fundingRounds={fundingRounds} />
          </ReportSection>

          {/* 3. Key People */}
          <ReportSection
            id={SECTION_IDS.people}
            title="Key People"
            confidence={getSectionConfidence(data, "people")}
            sourceCount={report.key_people?.source_count || getSectionSources(data, "people").length}
            sourceUrls={getSectionSources(data, "people")}
          >
            {people.length > 0 ? (
              <div className="grid gap-3 sm:grid-cols-2">
                {people.map((person, i) => (
                  <div
                    key={person.name || i}
                    className="flex items-start gap-3 rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--muted))]/20 p-4 hover-glow transition-all animate-init animate-fade-in-up"
                    style={{ animationDelay: `${i * 0.06}s` }}
                  >
                    <div className="rounded-full bg-gradient-to-br from-blue-500/12 to-purple-500/8 p-2.5">
                      <User className="h-4 w-4 text-blue-400" />
                    </div>
                    <div className="flex-1 min-w-0 space-y-0.5">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-medium text-[hsl(var(--foreground))] truncate">
                          {person.name || "Unknown"}
                        </p>
                        {person.linkedin_url && (
                          <a
                            href={person.linkedin_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-[hsl(var(--muted-foreground))] hover:text-[#0A66C2] transition-colors shrink-0 cursor-pointer"
                            aria-label={`${person.name} LinkedIn`}
                          >
                            <LinkedInIcon className="h-3.5 w-3.5" />
                          </a>
                        )}
                      </div>
                      {(person.title || person.role) && (
                        <p className="text-xs text-[hsl(var(--primary))]">
                          {person.title || person.role}
                        </p>
                      )}
                      {person.background && (
                        <p className="text-xs text-[hsl(var(--muted-foreground))] leading-relaxed mt-1">
                          {person.background}
                        </p>
                      )}
                      {/* Quality signals */}
                      <div className="flex flex-wrap gap-1.5 mt-2">
                        {person.prior_exits?.length > 0 && (
                          <span className="inline-flex items-center text-[10px] px-1.5 py-0.5 rounded-md border border-emerald-500/25 bg-emerald-500/5 text-emerald-400">
                            {person.prior_exits.length} exit{person.prior_exits.length > 1 ? "s" : ""}
                          </span>
                        )}
                        {person.domain_expertise_years && (
                          <span className="inline-flex items-center text-[10px] px-1.5 py-0.5 rounded-md border border-blue-500/25 bg-blue-500/5 text-blue-400">
                            {person.domain_expertise_years}+ yrs domain exp.
                          </span>
                        )}
                        {person.notable_affiliations?.length > 0 && (
                          <span className="inline-flex items-center text-[10px] px-1.5 py-0.5 rounded-md border border-purple-500/25 bg-purple-500/5 text-purple-400 truncate max-w-[200px]">
                            {person.notable_affiliations[0]}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : peopleText ? (
              <MarkdownProse content={peopleText} citations={report.citations || []} />
            ) : (
              <p className="text-sm text-[hsl(var(--muted-foreground))]">
                No key people data available.
              </p>
            )}
          </ReportSection>

          {/* 4. Product / Technology */}
          <ReportSection
            id={SECTION_IDS.product}
            title="Product / Technology"
            confidence={getSectionConfidence(data, "product")}
            sourceCount={report.product_technology?.source_count || getSectionSources(data, "product").length}
            sourceUrls={getSectionSources(data, "product")}
          >
            {productText ? (
              <MarkdownProse content={productText} citations={report.citations || []} />
            ) : (
              <p className="text-sm text-[hsl(var(--muted-foreground))]">
                No product/technology data available.
              </p>
            )}
          </ReportSection>

          {/* 5. Market Opportunity (due diligence) */}
          {hasMarket && (
            <ReportSection
              id={SECTION_IDS.market}
              title="Market Opportunity"
              confidence={getSectionConfidence(data, "market")}
              sourceCount={report.market_opportunity?.source_count || getSectionSources(data, "market").length}
              sourceUrls={getSectionSources(data, "market")}
            >
              <MarkdownProse content={textOf(report.market_opportunity)} citations={report.citations || []} />
            </ReportSection>
          )}

          {/* 6. Business Model (due diligence) */}
          {hasBusinessModel && (
            <ReportSection
              id={SECTION_IDS.businessModel}
              title="Business Model"
              confidence={getSectionConfidence(data, "businessModel")}
              sourceCount={report.business_model?.source_count || getSectionSources(data, "businessModel").length}
              sourceUrls={getSectionSources(data, "businessModel")}
            >
              <MarkdownProse content={textOf(report.business_model)} citations={report.citations || []} />
            </ReportSection>
          )}

          {/* 7. Competitive Advantages (due diligence) */}
          {hasCompetitiveAdvantages && (
            <ReportSection
              id={SECTION_IDS.competitiveAdvantages}
              title="Competitive Advantages"
              confidence={getSectionConfidence(data, "competitiveAdvantages")}
              sourceCount={report.competitive_advantages?.source_count || getSectionSources(data, "competitiveAdvantages").length}
              sourceUrls={getSectionSources(data, "competitiveAdvantages")}
            >
              <MarkdownProse content={textOf(report.competitive_advantages)} citations={report.citations || []} />
            </ReportSection>
          )}

          {/* 8. Traction (due diligence) */}
          {hasTraction && (
            <ReportSection
              id={SECTION_IDS.traction}
              title="Traction"
              confidence={getSectionConfidence(data, "traction")}
              sourceCount={report.traction?.source_count || getSectionSources(data, "traction").length}
              sourceUrls={getSectionSources(data, "traction")}
            >
              <MarkdownProse content={textOf(report.traction)} citations={report.citations || []} />
            </ReportSection>
          )}

          {/* 9. Recent News */}
          <ReportSection
            id={SECTION_IDS.news}
            title="Recent News"
            confidence={getSectionConfidence(data, "news")}
            sourceCount={report.recent_news?.source_count || getSectionSources(data, "news").length}
            sourceUrls={getSectionSources(data, "news")}
          >
            {newsItems.length > 0 ? (
              <div className="space-y-3">
                {newsItems.map((item, i) => (
                  <div
                    key={item.title || i}
                    className="animate-init animate-fade-in-up"
                    style={{ animationDelay: `${i * 0.06}s` }}
                  >
                    <NewsCard newsItem={item} />
                  </div>
                ))}
              </div>
            ) : newsText ? (
              <MarkdownProse content={newsText} citations={report.citations || []} />
            ) : (
              <p className="text-sm text-[hsl(var(--muted-foreground))]">
                No recent news available.
              </p>
            )}
          </ReportSection>

          {/* 10. Competitors */}
          <ReportSection
            id={SECTION_IDS.competitors}
            title="Competitors"
            confidence={getSectionConfidence(data, "competitors")}
            sourceCount={report.competitors?.source_count || getSectionSources(data, "competitors").length}
            sourceUrls={getSectionSources(data, "competitors")}
          >
            {competitorsText && (
              <div className="mb-4">
                <MarkdownProse content={competitorsText} citations={report.citations || []} />
              </div>
            )}
            {competitors.length > 0 ? (
              <CompetitorTable competitors={competitors} />
            ) : !competitorsText ? (
              <p className="text-sm text-[hsl(var(--muted-foreground))]">
                No competitor data available.
              </p>
            ) : null}
          </ReportSection>

          {/* 11. Risks (due diligence) */}
          {hasRisks && (
            <ReportSection
              id={SECTION_IDS.risks}
              title="Risks"
              confidence={getSectionConfidence(data, "risks")}
              sourceCount={report.risks?.source_count || getSectionSources(data, "risks").length}
              sourceUrls={getSectionSources(data, "risks")}
            >
              {risksText && (
                <div className="mb-4">
                  <MarkdownProse content={risksText} citations={report.citations || []} />
                </div>
              )}
              {riskEntries.length > 0 && (
                <div className="space-y-3">
                  {riskEntries.map((risk, i) => {
                    const RiskIcon = riskCategoryIcon[risk.category] || AlertTriangle;
                    const colors = severityColor[risk.severity] || severityColor.medium;
                    return (
                      <div
                        key={i}
                        className={`rounded-xl border p-4 ${colors} animate-init animate-fade-in-up`}
                        style={{ animationDelay: `${i * 0.06}s` }}
                      >
                        <div className="flex items-start gap-3">
                          <RiskIcon className="h-4 w-4 shrink-0 mt-0.5" />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="text-[10px] font-semibold uppercase tracking-wider">
                                {risk.category}
                              </span>
                              <span className="text-[10px] opacity-60">
                                {risk.severity} severity
                              </span>
                            </div>
                            <p className="text-sm leading-relaxed">{risk.content}</p>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </ReportSection>
          )}

          {/* 12. Red Flags */}
          <ReportSection
            id={SECTION_IDS.redFlags}
            title="Red Flags"
            confidence={getSectionConfidence(data, "red_flags")}
            sourceCount={report.red_flags?.source_count || getSectionSources(data, "red_flags").length}
            sourceUrls={getSectionSources(data, "red_flags")}
          >
            {redFlags.length > 0 ? (
              <div className="space-y-3">
                {redFlags.map((flag, i) => {
                  const flagText = typeof flag === "string" ? flag : flag.content || flag.text || "";
                  const flagConf = typeof flag === "object" ? flag.confidence : undefined;
                  const flagSources = typeof flag === "object" ? (flag.sources || flag.source_urls || []) : [];
                  return (
                    <div
                      key={i}
                      className="animate-init animate-fade-in-up"
                      style={{ animationDelay: `${i * 0.06}s` }}
                    >
                      <RedFlagCard
                        content={flagText}
                        confidence={flagConf}
                        sourceUrls={flagSources.map((s) =>
                          typeof s === "string" ? { url: s } : s
                        )}
                      />
                    </div>
                  );
                })}
              </div>
            ) : redFlagsText ? (
              <MarkdownProse content={redFlagsText} citations={report.citations || []} />
            ) : (
              <div className="flex items-center gap-2 text-sm text-emerald-400/80">
                <span className="h-2 w-2 rounded-full bg-emerald-400" />
                No red flags identified.
              </div>
            )}
          </ReportSection>
        </div>

        {/* Bottom spacer to prevent content from being hidden by agent log */}
        <div className="h-16" />
      </div>
    </div>
  );
}
