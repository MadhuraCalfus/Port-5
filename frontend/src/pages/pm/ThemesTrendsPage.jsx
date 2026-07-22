import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ArrowDownRight, ArrowUpRight, CheckCircle2, RefreshCw, Sparkles } from "lucide-react";
import { api } from "../../api";
import { Card } from "../../components/primitives";

// Same categorical PALETTE used for AnalyticsTab's category-breakdown bar
// chart — reused here for the same reason: distinct bars for distinct
// (specific, not generic) theme labels.
const PALETTE = ["#3d6b96", "#7fa8c9", "#9a9a9f", "#c0392b", "#b8860b", "#2f8f5b", "#5a5a5e", "#8a8a8f"];

const PERIOD_TYPES = [
  { id: "daily", label: "Daily" },
  { id: "weekly", label: "Weekly" },
  { id: "monthly", label: "Monthly" },
  { id: "yearly", label: "Yearly" },
];

// Status colors, not categorical identity — "up" (more complaints) reads as
// a warning regardless of which theme it is, "down" as good news, "new" as
// something to watch, "resolved" as fully good news.
const DIRECTION_STYLE = {
  up: { icon: ArrowUpRight, className: "text-red-600 dark:text-red-400" },
  down: { icon: ArrowDownRight, className: "text-emerald-600 dark:text-emerald-400" },
  flat: { icon: null, className: "text-ink/50 dark:text-ink-dark/50" },
  new: { icon: Sparkles, className: "text-amber-600 dark:text-amber-400" },
  resolved: { icon: CheckCircle2, className: "text-emerald-600 dark:text-emerald-400" },
};

function themeChartData(themeFrequency) {
  return Object.entries(themeFrequency)
    .sort((a, b) => b[1] - a[1])
    .map(([name, value]) => ({ name, value }));
}

export function ThemesTrendsPage() {
  const [periodType, setPeriodType] = useState("weekly");
  const [insights, setInsights] = useState(null);
  const [trend, setTrend] = useState(null);
  const [loading, setLoading] = useState(false);

  async function load(pt) {
    setLoading(true);
    try {
      const [i, t] = await Promise.all([api.pmInsights(pt), api.pmTrend(pt)]);
      setInsights(i);
      setTrend(t);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load(periodType);
  }, [periodType]);

  const chartData = insights ? themeChartData(insights.theme_frequency) : [];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-display text-lg font-semibold">Themes &amp; trends</h2>
        <div className="flex items-center gap-3">
          <div className="grid grid-cols-4 gap-1 rounded-xl bg-black/[0.04] dark:bg-white/[0.06] p-1">
            {PERIOD_TYPES.map(({ id, label }) => (
              <button
                key={id}
                type="button"
                onClick={() => setPeriodType(id)}
                className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                  periodType === id
                    ? "bg-surface dark:bg-surface-dark text-brand dark:text-brand-dim shadow-sm"
                    : "text-ink/50 dark:text-ink-dark/50 hover:text-ink dark:hover:text-ink-dark"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          <button
            onClick={() => load(periodType)}
            className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs text-ink/50 dark:text-ink-dark/50 hover:bg-black/5 dark:hover:bg-white/10"
          >
            <RefreshCw size={13} className={loading ? "animate-spin" : ""} /> Refresh
          </button>
        </div>
      </div>

      {!insights || !trend ? (
        <Card className="p-8 text-center text-sm text-ink/50 dark:text-ink-dark/50">Loading...</Card>
      ) : insights.total_items === 0 ? (
        <Card className="p-8 text-center text-sm text-ink/50 dark:text-ink-dark/50">
          No feedback for this period yet.
        </Card>
      ) : (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card className="p-5">
            <h3 className="mb-1 text-sm font-semibold">Theme frequency</h3>
            <p className="mb-3 text-xs text-ink/50 dark:text-ink-dark/50">
              {trend.current_period_start} – {trend.current_period_end}
            </p>
            {chartData.length === 0 ? (
              <p className="py-10 text-center text-sm text-ink/50 dark:text-ink-dark/50">No themes this period.</p>
            ) : (
              <ResponsiveContainer width="100%" height={Math.max(220, chartData.length * 34)}>
                <BarChart data={chartData} layout="vertical" margin={{ left: 24 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} opacity={0.15} />
                  <XAxis type="number" hide allowDecimals={false} />
                  <YAxis type="category" dataKey="name" width={150} tick={{ fontSize: 11 }} />
                  <Tooltip contentStyle={{ borderRadius: 12, border: "none", fontSize: 12 }} />
                  <Bar dataKey="value" radius={[0, 6, 6, 0]}>
                    {chartData.map((entry, i) => (
                      <Cell key={entry.name} fill={PALETTE[i % PALETTE.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </Card>

          <Card className="p-5">
            <h3 className="mb-1 text-sm font-semibold">Trends vs. previous {periodType.replace("ly", "")}</h3>
            <p className="mb-3 text-xs text-ink/50 dark:text-ink-dark/50">
              Compared to {trend.previous_period_key}
            </p>
            {trend.theme_deltas.length === 0 ? (
              <p className="py-10 text-center text-sm text-ink/50 dark:text-ink-dark/50">No theme changes to show.</p>
            ) : (
              <div className="thin-scroll max-h-[420px] space-y-2 overflow-y-auto pr-1">
                {trend.theme_deltas.map((d) => {
                  const style = DIRECTION_STYLE[d.direction] ?? DIRECTION_STYLE.flat;
                  const Icon = style.icon;
                  return (
                    <div
                      key={d.theme}
                      className="flex items-center justify-between gap-3 rounded-xl border border-black/8 dark:border-white/10 px-3.5 py-2.5"
                    >
                      <div>
                        <p className="text-sm font-medium text-ink dark:text-ink-dark">{d.theme}</p>
                        <p className="text-[11px] text-ink/50 dark:text-ink-dark/50">
                          {d.current_count} this period · {d.previous_count} previous
                        </p>
                      </div>
                      <span className={`inline-flex items-center gap-1 text-sm font-semibold ${style.className}`}>
                        {Icon && <Icon size={15} />}
                        {d.direction === "new"
                          ? "New"
                          : d.direction === "resolved"
                            ? "Resolved"
                            : d.direction === "flat"
                              ? "No change"
                              : `${d.delta_pct > 0 ? "+" : ""}${d.delta_pct}%`}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
