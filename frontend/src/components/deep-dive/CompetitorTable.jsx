/**
 * Simple table showing competitor companies.
 *
 * Props:
 *  - competitors: Array of { name, description, funding, differentiator }
 */
export default function CompetitorTable({ competitors = [] }) {
  if (competitors.length === 0) {
    return (
      <p className="text-sm text-[hsl(var(--muted-foreground))] italic">
        No competitor data available.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[hsl(var(--border))]">
            <th className="py-2 pr-4 text-left font-medium text-[hsl(var(--muted-foreground))]">
              Company
            </th>
            <th className="py-2 pr-4 text-left font-medium text-[hsl(var(--muted-foreground))]">
              Description
            </th>
            <th className="py-2 pr-4 text-left font-medium text-[hsl(var(--muted-foreground))]">
              Funding
            </th>
            <th className="py-2 text-left font-medium text-[hsl(var(--muted-foreground))]">
              Differentiator
            </th>
          </tr>
        </thead>
        <tbody>
          {competitors.map((comp, i) => (
            <tr
              key={comp.name || i}
              className={
                i % 2 === 0
                  ? "bg-transparent"
                  : "bg-[hsl(var(--muted))]/30"
              }
            >
              <td className="py-2.5 pr-4 font-medium text-[hsl(var(--foreground))] whitespace-nowrap">
                {comp.name || "Unknown"}
              </td>
              <td className="py-2.5 pr-4 text-[hsl(var(--muted-foreground))] max-w-xs">
                {comp.description || "—"}
              </td>
              <td className="py-2.5 pr-4 text-[hsl(var(--foreground))] whitespace-nowrap">
                {comp.funding || "—"}
              </td>
              <td className="py-2.5 text-[hsl(var(--muted-foreground))] max-w-xs">
                {comp.differentiator || "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
