import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { useMemo } from "react";

/**
 * Format a number as a compact funding string, e.g. "$12.5M"
 */
function formatAmount(value) {
  if (value == null) return "N/A";
  if (value >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(1)}B`;
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(0)}K`;
  return `$${value}`;
}

/**
 * Custom tooltip for funding chart hover state.
 */
function ChartTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const data = payload[0].payload;
  return (
    <div className="rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--popover))] p-3 text-xs shadow-lg">
      <p className="font-semibold text-[hsl(var(--foreground))]">{data.stage}</p>
      <p className="text-[hsl(var(--muted-foreground))]">{data.date}</p>
      <p className="mt-1 text-emerald-400 font-medium">{formatAmount(data.amount)}</p>
      {data.investors && (
        <p className="mt-1 text-[hsl(var(--muted-foreground))] leading-relaxed">
          {data.investors}
        </p>
      )}
    </div>
  );
}

/**
 * AreaChart showing funding rounds over time with a table below.
 *
 * Props:
 *  - fundingRounds: Array of { date, stage, amount, investors }
 *    where amount is a number and investors is a string or array
 */
export default function FundingChart({ fundingRounds = [] }) {
  const chartData = useMemo(() => {
    if (!fundingRounds.length) return [];

    // Sort by date ascending
    const sorted = [...fundingRounds].sort(
      (a, b) => new Date(a.date) - new Date(b.date)
    );

    // Build cumulative funding
    let cumulative = 0;
    return sorted.map((round) => {
      const amt = Number(round.amount) || 0;
      cumulative += amt;
      const investors = Array.isArray(round.investors)
        ? round.investors.join(", ")
        : round.investors || "";
      return {
        date: round.date,
        stage: round.stage || "Unknown",
        amount: amt,
        cumulative,
        investors,
      };
    });
  }, [fundingRounds]);

  if (fundingRounds.length === 0) {
    return (
      <p className="text-sm text-[hsl(var(--muted-foreground))] italic">
        No funding data available.
      </p>
    );
  }

  return (
    <div className="space-y-6">
      {/* Chart */}
      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="fundingGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="hsl(240 3.7% 15.9%)"
              vertical={false}
            />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11, fill: "hsl(240 5% 64.9%)" }}
              tickLine={false}
              axisLine={{ stroke: "hsl(240 3.7% 15.9%)" }}
            />
            <YAxis
              tickFormatter={formatAmount}
              tick={{ fontSize: 11, fill: "hsl(240 5% 64.9%)" }}
              tickLine={false}
              axisLine={false}
              width={60}
            />
            <Tooltip content={<ChartTooltip />} />
            <Area
              type="monotone"
              dataKey="cumulative"
              stroke="#10b981"
              strokeWidth={2}
              fill="url(#fundingGradient)"
              dot={{ r: 4, fill: "#10b981", strokeWidth: 0 }}
              activeDot={{ r: 6, fill: "#10b981", stroke: "#fff", strokeWidth: 2 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Rounds table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[hsl(var(--border))]">
              <th className="py-2 pr-4 text-left font-medium text-[hsl(var(--muted-foreground))]">
                Date
              </th>
              <th className="py-2 pr-4 text-left font-medium text-[hsl(var(--muted-foreground))]">
                Stage
              </th>
              <th className="py-2 pr-4 text-right font-medium text-[hsl(var(--muted-foreground))]">
                Amount
              </th>
              <th className="py-2 text-left font-medium text-[hsl(var(--muted-foreground))]">
                Investors
              </th>
            </tr>
          </thead>
          <tbody>
            {chartData.map((round, i) => (
              <tr
                key={i}
                className={
                  i % 2 === 0
                    ? "bg-transparent"
                    : "bg-[hsl(var(--muted))]/30"
                }
              >
                <td className="py-2 pr-4 text-[hsl(var(--foreground))]">
                  {round.date}
                </td>
                <td className="py-2 pr-4 text-[hsl(var(--foreground))]">
                  {round.stage}
                </td>
                <td className="py-2 pr-4 text-right text-emerald-400 font-medium">
                  {formatAmount(round.amount)}
                </td>
                <td className="py-2 text-[hsl(var(--muted-foreground))]">
                  {round.investors || "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
