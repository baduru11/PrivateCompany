import { X, ArrowRight, Building2, Calendar, MapPin, DollarSign, Users, ExternalLink } from "lucide-react";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { ScrollArea } from "../ui/scroll-area";
import { cn } from "../../lib/utils";

function ConfidenceBadge({ confidence }) {
  if (confidence == null) return null;
  const pct = typeof confidence === "number" ? confidence : 0;
  let color = "bg-red-500/12 text-red-400 border-red-500/25";
  if (pct >= 0.8) {
    color = "bg-emerald-500/12 text-emerald-400 border-emerald-500/25";
  } else if (pct >= 0.5) {
    color = "bg-amber-500/12 text-amber-400 border-amber-500/25";
  }

  return (
    <Badge variant="outline" className={cn("text-[10px] font-mono tabular-nums", color)}>
      {Math.round(pct * 100)}% confidence
    </Badge>
  );
}

export default function CompanySidebar({
  company,
  isOpen = false,
  onClose,
  onDeepDive,
}) {
  if (!company && !isOpen) return null;

  const detail = (Icon, label, value) => {
    if (!value) return null;
    return (
      <div className="flex items-start gap-2.5 py-2.5 border-b border-[hsl(var(--border))]/30 last:border-0">
        <div className="p-1.5 rounded-md bg-[hsl(var(--muted))]">
          <Icon className="w-3.5 h-3.5 text-[hsl(var(--muted-foreground))]" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-[10px] uppercase tracking-wider text-[hsl(var(--muted-foreground))]/70 mb-0.5">
            {label}
          </p>
          <p className="text-sm text-[hsl(var(--foreground))]">{value}</p>
        </div>
      </div>
    );
  };

  return (
    <div
      className={cn(
        "fixed top-0 right-0 h-full w-80 z-30",
        "glass-strong border-l border-[hsl(var(--border))]",
        "shadow-2xl shadow-black/30",
        "transition-transform duration-300 ease-in-out",
        isOpen ? "translate-x-0" : "translate-x-full"
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3.5 border-b border-[hsl(var(--border))]">
        <h2 className="text-sm font-semibold text-[hsl(var(--foreground))] truncate">
          {company?.name || "Company Details"}
        </h2>
        <button
          onClick={onClose}
          aria-label="Close sidebar"
          className="p-1.5 rounded-lg hover:bg-[hsl(var(--muted))] transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--ring))]"
        >
          <X className="w-4 h-4 text-[hsl(var(--muted-foreground))]" />
        </button>
      </div>

      {/* Content */}
      {company && (
        <ScrollArea className="h-[calc(100%-3.5rem)]">
          <div className="p-4 space-y-4 animate-fade-in">
            {/* Name and confidence */}
            <div>
              <h3 className="text-lg font-semibold text-[hsl(var(--foreground))] leading-tight">
                {company.name}
              </h3>
              <div className="flex items-center gap-2 mt-2 flex-wrap">
                {company.sub_sector && (
                  <Badge variant="outline" className="text-[10px] text-[hsl(var(--muted-foreground))]">
                    {company.sub_sector}
                  </Badge>
                )}
                {company.confidence != null && (
                  <ConfidenceBadge confidence={company.confidence} />
                )}
              </div>
            </div>

            {/* Website link */}
            {company.website && (
              <a
                href={company.website}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 text-sm text-blue-400 hover:text-blue-300 transition-colors"
              >
                <ExternalLink className="w-3.5 h-3.5" />
                {company.website.replace(/^https?:\/\//, "").replace(/\/$/, "")}
              </a>
            )}

            {/* Description */}
            {company.description && (
              <p className="text-sm text-[hsl(var(--muted-foreground))] leading-relaxed">
                {company.description}
              </p>
            )}

            {/* Details list */}
            <div className="space-y-0 rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--background))]/50 p-3">
              {detail(DollarSign, "Funding", company.funding || company.funding_amount)}
              {detail(Building2, "Stage", company.funding_stage || company.stage)}
              {detail(Calendar, "Founded", company.founding_year || company.founded)}
              {detail(MapPin, "Headquarters", company.headquarters || company.hq)}
              {detail(
                Users,
                "Key Investors",
                Array.isArray(company.key_investors)
                  ? company.key_investors.join(", ")
                  : company.key_investors
              )}
            </div>

            {/* Deep Dive button */}
            <Button
              onClick={() => onDeepDive?.(company)}
              className={cn(
                "w-full mt-2 rounded-lg font-medium cursor-pointer",
                "bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700",
                "text-white shadow-lg shadow-blue-500/20 hover:shadow-blue-500/30",
                "transition-all duration-200"
              )}
            >
              Deep Dive
              <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
          </div>
        </ScrollArea>
      )}
    </div>
  );
}
