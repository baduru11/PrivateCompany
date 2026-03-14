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
import { cn } from "../../lib/utils";

function parseAmount(raw) {
  if (raw == null) return 0;
  if (typeof raw === "number") return raw;
  const str = String(raw).trim();
  const match = str.match(/\$?\s*~?\s*([\d,.]+)\s*(T|B|M|K)?/i);
  if (!match) return 0;
  let num = parseFloat(match[1].replace(/,/g, ""));
  if (isNaN(num)) return 0;
  const suffix = (match[2] || "").toUpperCase();
  if (suffix === "T") num *= 1_000_000_000_000;
  else if (suffix === "B") num *= 1_000_000_000;
  else if (suffix === "M") num *= 1_000_000;
  else if (suffix === "K") num *= 1_000;
  return num;
}

function formatAmount(value) {
  if (value == null) return "N/A";
  if (value >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(1)}B`;
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(0)}K`;
  return `$${value}`;
}

function ChartTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const data = payload[0].payload;
  return (
    <div className="rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--popover))] p-3.5 text-xs shadow-xl">
      <p className="font-semibold text-[hsl(var(--foreground))]">{data.stage}</p>
      <p className="text-[hsl(var(--muted-foreground))]">{data.date}</p>
      <p className="mt-1.5 text-emerald-400 font-semibold text-sm">{formatAmount(data.amount)}</p>
      {data.investors && (
        <p className="mt-1 text-[hsl(var(--muted-foreground))] leading-relaxed">
          {data.investors}
        </p>
      )}
    </div>
  );
}

export default function FundingChart({ fundingRounds = [] }) {
  const chartData = useMemo(() => {
    if (!fundingRounds.length) return [];

    // Backend already deduplicates — just sort and compute cumulative
    const sorted = [...fundingRounds].sort(
      (a, b) => new Date(a.date) - new Date(b.date)
    );
    let cumulative = 0;
    return sorted.map((round) => {
      const amt = parseAmount(round.amount);
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
        lead_investor: round.lead_investor || "",
        pre_money_valuation: round.pre_money_valuation || "",
        post_money_valuation: round.post_money_valuation || "",
      };
    });
  }, [fundingRounds]);

  if (fundingRounds.length === 0) {
    return (
      <p className="text-sm text-[hsl(var(--muted-foreground))]">
        No funding data available.
      </p>
    );
  }

  return (
    <div className="space-y-6">
      {/* Chart — only show when there are 2+ rounds (single point renders nothing visible) */}
      {chartData.length >= 2 && (
        <div className="h-64 w-full rounded-lg bg-[hsl(var(--background))]/50 p-2">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="fundingGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.25} />
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="hsl(217 33% 14%)"
                vertical={false}
              />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 11, fill: "hsl(215 20% 55%)" }}
                tickLine={false}
                axisLine={{ stroke: "hsl(217 33% 14%)" }}
              />
              <YAxis
                tickFormatter={formatAmount}
                tick={{ fontSize: 11, fill: "hsl(215 20% 55%)" }}
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
      )}

      {/* Rounds table */}
      <div className="overflow-x-auto rounded-lg border border-[hsl(var(--border))]">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[hsl(var(--border))] bg-[hsl(var(--muted))]/30">
              <th className="py-2.5 px-4 text-left text-[10px] font-semibold uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
                Date
              </th>
              <th className="py-2.5 px-4 text-left text-[10px] font-semibold uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
                Stage
              </th>
              <th className="py-2.5 px-4 text-right text-[10px] font-semibold uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
                Amount
              </th>
              <th className="py-2.5 px-4 text-left text-[10px] font-semibold uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
                Lead Investor
              </th>
              <th className="py-2.5 px-4 text-left text-[10px] font-semibold uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
                Investors
              </th>
              <th className="py-2.5 px-4 text-right text-[10px] font-semibold uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
                Pre-Money
              </th>
              <th className="py-2.5 px-4 text-right text-[10px] font-semibold uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
                Post-Money
              </th>
            </tr>
          </thead>
          <tbody>
            {chartData.map((round, i) => (
              <tr
                key={i}
                className={cn(
                  "border-b border-[hsl(var(--border))]/30 last:border-0 transition-colors hover:bg-[hsl(var(--accent))]/30",
                  i % 2 === 0 ? "bg-transparent" : "bg-[hsl(var(--muted))]/15"
                )}
              >
                <td className="py-2.5 px-4 text-[hsl(var(--foreground))] tabular-nums">
                  {round.date}
                </td>
                <td className="py-2.5 px-4 text-[hsl(var(--foreground))]">
                  {round.stage}
                </td>
                <td className="py-2.5 px-4 text-right text-emerald-400 font-medium tabular-nums">
                  {formatAmount(round.amount)}
                </td>
                <td className="py-2.5 px-4 text-[hsl(var(--foreground))]">
                  {round.lead_investor || "\u2014"}
                </td>
                <td className="py-2.5 px-4 text-[hsl(var(--muted-foreground))]">
                  {round.investors || "\u2014"}
                </td>
                <td className="py-2.5 px-4 text-right text-[hsl(var(--muted-foreground))] tabular-nums">
                  {round.pre_money_valuation || "\u2014"}
                </td>
                <td className="py-2.5 px-4 text-right text-[hsl(var(--muted-foreground))] tabular-nums">
                  {round.post_money_valuation || "\u2014"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
