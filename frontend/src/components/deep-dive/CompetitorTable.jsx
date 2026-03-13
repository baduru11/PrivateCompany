import { ExternalLink } from "lucide-react";
import { cn } from "../../lib/utils";

export default function CompetitorTable({ competitors = [] }) {
  if (competitors.length === 0) {
    return (
      <p className="text-sm text-[hsl(var(--muted-foreground))]">
        No competitor data available.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-[hsl(var(--border))]">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[hsl(var(--border))] bg-[hsl(var(--muted))]/30">
            <th className="py-2.5 px-4 text-left text-[10px] font-semibold uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
              Company
            </th>
            <th className="py-2.5 px-4 text-left text-[10px] font-semibold uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
              Description
            </th>
            <th className="py-2.5 px-4 text-left text-[10px] font-semibold uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
              Funding
            </th>
            <th className="py-2.5 px-4 text-left text-[10px] font-semibold uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
              Overlap
            </th>
            <th className="py-2.5 px-4 text-left text-[10px] font-semibold uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
              Differentiator
            </th>
          </tr>
        </thead>
        <tbody>
          {competitors.map((comp, i) => (
            <tr
              key={comp.name || i}
              className={cn(
                "border-b border-[hsl(var(--border))]/30 last:border-0 transition-colors hover:bg-[hsl(var(--accent))]/30",
                i % 2 === 0 ? "bg-transparent" : "bg-[hsl(var(--muted))]/15"
              )}
            >
              <td className="py-3 px-4 font-medium text-[hsl(var(--foreground))] whitespace-nowrap">
                <div className="flex items-center gap-2">
                  <span>{comp.name || "Unknown"}</span>
                  {comp.website && (
                    <a
                      href={comp.website}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--primary))] transition-colors"
                      aria-label={`Visit ${comp.name} website`}
                    >
                      <ExternalLink className="h-3 w-3" />
                    </a>
                  )}
                </div>
                {comp.funding_stage && (
                  <span className="text-[10px] text-[hsl(var(--muted-foreground))] block mt-0.5">
                    {comp.funding_stage}
                  </span>
                )}
              </td>
              <td className="py-3 px-4 text-[hsl(var(--muted-foreground))] max-w-xs leading-relaxed">
                {comp.description || "\u2014"}
              </td>
              <td className="py-3 px-4 text-[hsl(var(--foreground))] whitespace-nowrap tabular-nums">
                {comp.funding || "\u2014"}
              </td>
              <td className="py-3 px-4 text-[hsl(var(--muted-foreground))] max-w-xs leading-relaxed">
                {comp.overlap || "\u2014"}
              </td>
              <td className="py-3 px-4 text-[hsl(var(--muted-foreground))] max-w-xs leading-relaxed">
                {comp.differentiator || "\u2014"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
