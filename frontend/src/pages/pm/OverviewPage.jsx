import { useEffect, useState } from "react";
import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { ClipboardList, RefreshCw, Star, Ticket } from "lucide-react";
import { api } from "../../api";
import { Card } from "../../components/primitives";

// Same categorical hex values used throughout AnalyticsTab.jsx (Priority/
// Status/Mode charts), plus a re-stepped neutral (validated with
// scripts/validate_palette.js — the stock slate-500 #64748b sat too close to
// the green for normal color vision at this 4-color size).
const SENTIMENT_COLORS = { positive: "#2f8f5b", neutral: "#556270", mixed: "#b8860b", negative: "#c0392b" };
const SENTIMENT_ORDER = ["positive", "neutral", "mixed", "negative"];

function toOrderedChartData(breakdown, order) {
  return order.filter((k) => breakdown[k] != null).map((k) => ({ name: k, value: breakdown[k] }));
}

const SOURCE_ICONS = { ticket: Ticket, review: Star, survey: ClipboardList };
const SOURCE_LABELS = { ticket: "Tickets", review: "Reviews", survey: "Surveys" };

export function OverviewPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      setData(await api.pmInsights("weekly"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  if (!data) {
    return <Card className="p-8 text-center text-sm text-ink/50 dark:text-ink-dark/50">Loading...</Card>;
  }

  const sentimentData = toOrderedChartData(data.sentiment_distribution, SENTIMENT_ORDER);
  const periodLabel = `${new Date(data.period_start + "T00:00:00").toLocaleDateString(undefined, { month: "short", day: "numeric" })} – ${new Date(
    data.period_end + "T00:00:00",
  ).toLocaleDateString(undefined, { month: "short", day: "numeric" })}`;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-display text-lg font-semibold">Customer voice overview</h2>
          <p className="text-xs text-ink/50 dark:text-ink-dark/50">This week · {periodLabel}</p>
        </div>
        <button
          onClick={load}
          className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs text-ink/50 dark:text-ink-dark/50 hover:bg-black/5 dark:hover:bg-white/10"
        >
          <RefreshCw size={13} className={loading ? "animate-spin" : ""} /> Refresh
        </button>
      </div>

      {data.total_items === 0 ? (
        <Card className="p-8 text-center text-sm text-ink/50 dark:text-ink-dark/50">
          No feedback yet this week — submitted tickets, surveys, and imported reviews will show up here.
        </Card>
      ) : (
        <>
          <div>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink/50 dark:text-ink-dark/50">
              Customer voice
            </h3>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <StatCard label="Total this week" value={String(data.total_items)} highlight />
              {["ticket", "review", "survey"].map((source) => {
                const Icon = SOURCE_ICONS[source];
                return (
                  <StatCard
                    key={source}
                    label={SOURCE_LABELS[source]}
                    value={String(data.source_breakdown[source] ?? 0)}
                    icon={Icon}
                  />
                );
              })}
            </div>
          </div>

          <div>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink/50 dark:text-ink-dark/50">
              AI analysis
            </h3>
            <div className="grid gap-6 lg:grid-cols-2">
              <Card className="p-5">
                <h4 className="mb-3 text-sm font-semibold">Sentiment distribution</h4>
                {sentimentData.length === 0 ? (
                  <p className="py-10 text-center text-sm text-ink/50 dark:text-ink-dark/50">No sentiment data yet.</p>
                ) : (
                  <ResponsiveContainer width="100%" height={240}>
                    <PieChart>
                      <Pie data={sentimentData} dataKey="value" nameKey="name" innerRadius={50} outerRadius={85} paddingAngle={2}>
                        {sentimentData.map((entry) => (
                          <Cell key={entry.name} fill={SENTIMENT_COLORS[entry.name] ?? "#556270"} />
                        ))}
                      </Pie>
                      <Legend verticalAlign="bottom" height={24} wrapperStyle={{ fontSize: 11, textTransform: "capitalize" }} />
                      <Tooltip contentStyle={{ borderRadius: 12, border: "none", fontSize: 12 }} />
                    </PieChart>
                  </ResponsiveContainer>
                )}
              </Card>

              <div className="grid grid-cols-2 gap-3 content-start">
                <StatCard
                  label="Avg. sentiment"
                  value={`${data.avg_sentiment_score >= 0 ? "+" : ""}${data.avg_sentiment_score.toFixed(2)}`}
                  sub="-1 (very negative) to +1 (very positive)"
                />
                <StatCard
                  label="Avg. urgency"
                  value={`${Math.round(data.avg_urgency_score * 100)}%`}
                  sub="0 (no urgency) to 100 (act now)"
                />
                <StatCard
                  label="Needs follow-up"
                  value={String(data.actionable_count)}
                  sub={`of ${data.total_items} items this week`}
                  highlight={data.actionable_count > 0}
                />
                <StatCard label="Distinct themes" value={String(Object.keys(data.theme_frequency).length)} sub="see Themes & Trends" />
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function StatCard({ label, value, sub, icon: Icon, highlight }) {
  return (
    <Card className={`p-4 text-center ${highlight ? "ring-2 ring-brand/40" : ""}`}>
      {Icon && <Icon size={16} className="mx-auto mb-1 text-ink/40 dark:text-ink-dark/40" />}
      <div className={`font-display text-2xl font-bold ${highlight ? "text-brand dark:text-brand-dim" : ""}`}>{value}</div>
      <div className="text-[11px] uppercase tracking-wide text-ink/40 dark:text-ink-dark/40">{label}</div>
      {sub && <div className="mt-0.5 text-[11px] text-ink/40 dark:text-ink-dark/40">{sub}</div>}
    </Card>
  );
}
