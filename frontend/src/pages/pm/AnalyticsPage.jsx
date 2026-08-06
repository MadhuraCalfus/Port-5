import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { CalendarRange, FileDown, Loader2, RefreshCw } from "lucide-react";
import { api } from "../../api";
import { Card } from "../../components/primitives";
import { generateAnalyticsExportPdf } from "../../pmReportExport";
import { MONTHS, dayKey, daysInMonth, isoWeekKey, weeksInMonth, yearOptions } from "../../periodNav";

const PERIOD_TYPES = [
  { id: "daily", label: "Daily" },
  { id: "weekly", label: "Weekly" },
  { id: "monthly", label: "Monthly" },
  { id: "yearly", label: "Yearly" },
];

function isoDate(d) {
  return d.toISOString().slice(0, 10);
}

// Re-stepped neutral gray, validated with the dataviz skill's palette
// checker — the stock slate-500 (#64748b) used elsewhere in this app sat
// too close to green for normal color vision at this 4-color size.
const SENTIMENT_COLORS = { positive: "#2f8f5b", neutral: "#556270", negative: "#c0392b" };
const SENTIMENT_ORDER = ["positive", "neutral", "negative"];

// Fixed-order categorical palette for the 11 real feedback categories,
// validated with the dataviz skill's checker (adjacent-pair CVD >= 8,
// normal-vision >= 15, chroma floor, lightness band — see
// scripts/validate_palette.js). "Other" deliberately does NOT get its own
// hue: per the skill's own rule, a category beyond the validated set folds
// to a neutral rather than a generated color, which is exactly what that
// bucket already is.
const CATEGORY_COLORS = {
  "Product Quality & Fit": "#eda100",
  "Packaging & Damage": "#eb6834",
  "Delivery & Logistics": "#a8541a",
  "Review & App Flow Friction": "#2a78d6",
  "Authenticity & Trust": "#1baf7a",
  "Personalization Mismatch": "#0891b2",
  "Pricing & Offers": "#e34948",
  "Rewards & Loyalty": "#008300",
  "Customer Support": "#e87ba4",
};
const OTHER_CATEGORY_COLOR = "#898781";
const categoryColor = (category) => CATEGORY_COLORS[category] ?? OTHER_CATEGORY_COLOR;

function toOrderedChartData(breakdown, order) {
  return order.filter((k) => breakdown[k] != null).map((k) => ({ name: k, value: breakdown[k] }));
}

// Plain absolute counts for this period — total feedback, sentiment split,
// actionable count, and the averages, all for whatever period/date filter
// is currently selected.
function StatTile({ label, value, tone, sub }) {
  const toneClass =
    tone === "good"
      ? "text-emerald-600 dark:text-emerald-400"
      : tone === "bad"
        ? "text-red-600 dark:text-red-400"
        : "text-ink dark:text-ink-dark";
  return (
    <Card className="p-3.5">
      <p className="text-[11px] uppercase tracking-wide text-ink/40 dark:text-ink-dark/40">{label}</p>
      <p className={`mt-1 font-display text-xl font-bold ${toneClass}`}>{value}</p>
      {sub && <p className="mt-0.5 text-[11px] text-ink/40 dark:text-ink-dark/40">{sub}</p>}
    </Card>
  );
}

// Category-level detail (which category is most mentioned, most negative,
// etc.) lives on the Category Insights tab — this page is the general
// pulse: overall sentiment/volume/rating trends, where feedback comes from,
// and — up top — which category dominates this period and what it's about.
export function AnalyticsPage() {
  const [periodType, setPeriodType] = useState("weekly");
  const [selectedYear, setSelectedYear] = useState(() => new Date().getFullYear());
  const [selectedMonth, setSelectedMonth] = useState(() => new Date().getMonth() + 1);
  const [selectedWeekKey, setSelectedWeekKey] = useState(() => isoWeekKey(new Date()));
  const [selectedDayKey, setSelectedDayKey] = useState(() => dayKey(new Date()));

  // A custom date range is mutually exclusive with the Daily/Weekly/
  // Monthly/Yearly buckets — there's no "previous range" to compare
  // against, so trend/series data doesn't exist while this is active.
  const [isCustomRange, setIsCustomRange] = useState(false);
  const [rangeStart, setRangeStart] = useState(() => isoDate(new Date(Date.now() - 29 * 86400000)));
  const [rangeEnd, setRangeEnd] = useState(() => isoDate(new Date()));

  // Which category's theme breakdown the second chart shows — null means
  // "follow the auto-computed top category," any other value is the PM
  // explicitly picking a different one from the dropdown.
  const [themeCategory, setThemeCategory] = useState(null);

  const [insights, setInsights] = useState(null);
  const [trend, setTrend] = useState(null);
  const [series, setSeries] = useState(null);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(null); // "pdf" | "csv" | null
  const [error, setError] = useState(null);

  const yearOptionsList = useMemo(() => yearOptions(), []);
  const weekOptions = useMemo(() => weeksInMonth(selectedYear, selectedMonth), [selectedYear, selectedMonth]);
  const dayOptions = useMemo(() => daysInMonth(selectedYear, selectedMonth), [selectedYear, selectedMonth]);

  // Keep the selected week/day valid whenever the year/month narrows their options.
  useEffect(() => {
    if (weekOptions.length > 0 && !weekOptions.some((w) => w.key === selectedWeekKey)) {
      setSelectedWeekKey(weekOptions[0].key);
    }
  }, [weekOptions, selectedWeekKey]);
  useEffect(() => {
    if (dayOptions.length > 0 && !dayOptions.some((d) => d.key === selectedDayKey)) {
      setSelectedDayKey(dayOptions[0].key);
    }
  }, [dayOptions, selectedDayKey]);

  const periodKey =
    periodType === "yearly"
      ? String(selectedYear)
      : periodType === "monthly"
        ? `${selectedYear}-${String(selectedMonth).padStart(2, "0")}`
        : periodType === "weekly"
          ? selectedWeekKey
          : selectedDayKey;

  async function load() {
    setLoading(true);
    try {
      if (isCustomRange) {
        const i = await api.pmInsightsRange(rangeStart, rangeEnd);
        setInsights(i);
        setTrend(null);
        setSeries(null);
      } else {
        const [i, t, s] = await Promise.all([api.pmInsights(periodType, periodKey), api.pmTrend(periodType, periodKey), api.pmSentimentSeries(periodType, 8, periodKey)]);
        setInsights(i);
        setTrend(t);
        setSeries(s.series);
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isCustomRange, periodType, periodKey, rangeStart, rangeEnd]);

  function toggleCustomRange() {
    setIsCustomRange((prev) => !prev);
  }

  async function exportPdf() {
    if (!insights) return;
    setExporting("pdf");
    setError(null);
    try {
      generateAnalyticsExportPdf({ periodType: isCustomRange ? "custom" : periodType, insights, trend });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setExporting(null);
    }
  }

  const sentimentData = insights ? toOrderedChartData(insights.sentiment_distribution, SENTIMENT_ORDER) : [];

  const ratingChartData = insights
    ? [1, 2, 3, 4, 5].map((star) => ({ star, label: `${star}★`, count: insights.rating_distribution[star] ?? 0 }))
    : [];
  const ratingColor = (star) => (star >= 4 ? "#2f8f5b" : star === 3 ? "#b8860b" : "#c0392b");

  const volumeSeriesData = series ?? [];

  // null (not 0) for periods with no rated surveys, so the line has a gap
  // there instead of falsely dipping to zero stars.
  const ratingSeriesData = (series ?? []).map((s) => ({ ...s, avg_rating: s.rated_count > 0 ? s.avg_rating : null }));

  const categoryRanking = insights?.category_urgency_ranking ?? [];
  const categoryVolumeData = [...categoryRanking].sort((a, b) => b.count - a.count).slice(0, 10).map((t) => ({ category: t.category, count: t.count }));

  const topCategory = insights?.top_category ?? null;
  // Fall back to the auto top category if the PM's picked category has no
  // data in whatever period/range is now selected.
  const themeCategoryEntry =
    categoryRanking.find((c) => c.category === themeCategory) ?? categoryRanking.find((c) => c.category === topCategory?.category) ?? null;
  const topCategoryThemesData = themeCategoryEntry ? themeCategoryEntry.themes.map((t) => ({ theme: t.theme, count: t.count })) : [];
  const categoryOptionsSorted = [...categoryRanking].sort((a, b) => b.count - a.count);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-display text-lg font-semibold">Analytics</h2>
        <div className="flex flex-wrap items-center gap-3">
          {isCustomRange ? (
            <>
              <input
                type="date"
                value={rangeStart}
                max={rangeEnd}
                onChange={(e) => setRangeStart(e.target.value)}
                className="rounded-lg border border-black/10 dark:border-white/15 bg-transparent px-2 py-1.5 text-xs text-ink dark:text-ink-dark"
              />
              <span className="text-xs text-ink/40 dark:text-ink-dark/40">to</span>
              <input
                type="date"
                value={rangeEnd}
                min={rangeStart}
                max={isoDate(new Date())}
                onChange={(e) => setRangeEnd(e.target.value)}
                className="rounded-lg border border-black/10 dark:border-white/15 bg-transparent px-2 py-1.5 text-xs text-ink dark:text-ink-dark"
              />
            </>
          ) : (
            <>
              <select
                value={selectedYear}
                onChange={(e) => setSelectedYear(Number(e.target.value))}
                className="rounded-lg border border-black/10 dark:border-white/15 bg-transparent px-2 py-1.5 text-xs text-ink dark:text-ink-dark"
              >
                {yearOptionsList.map((y) => (
                  <option key={y} value={y}>
                    {y}
                  </option>
                ))}
              </select>

              {(periodType === "monthly" || periodType === "weekly" || periodType === "daily") && (
                <select
                  value={selectedMonth}
                  onChange={(e) => setSelectedMonth(Number(e.target.value))}
                  className="rounded-lg border border-black/10 dark:border-white/15 bg-transparent px-2 py-1.5 text-xs text-ink dark:text-ink-dark"
                >
                  {MONTHS.map((m, i) => (
                    <option key={m} value={i + 1}>
                      {m}
                    </option>
                  ))}
                </select>
              )}

              {periodType === "weekly" && (
                <select
                  value={selectedWeekKey}
                  onChange={(e) => setSelectedWeekKey(e.target.value)}
                  className="rounded-lg border border-black/10 dark:border-white/15 bg-transparent px-2 py-1.5 text-xs text-ink dark:text-ink-dark"
                >
                  {weekOptions.map((w) => (
                    <option key={w.key} value={w.key}>
                      {w.label}
                    </option>
                  ))}
                </select>
              )}

              {periodType === "daily" && (
                <select
                  value={selectedDayKey}
                  onChange={(e) => setSelectedDayKey(e.target.value)}
                  className="rounded-lg border border-black/10 dark:border-white/15 bg-transparent px-2 py-1.5 text-xs text-ink dark:text-ink-dark"
                >
                  {dayOptions.map((d) => (
                    <option key={d.key} value={d.key}>
                      {d.label}
                    </option>
                  ))}
                </select>
              )}
            </>
          )}

          <div className="grid grid-cols-4 gap-1 rounded-xl bg-black/[0.04] dark:bg-white/[0.06] p-1">
            {PERIOD_TYPES.map(({ id, label }) => (
              <button
                key={id}
                type="button"
                disabled={isCustomRange}
                onClick={() => setPeriodType(id)}
                className={`rounded-lg px-3 py-1.5 text-xs font-medium transition disabled:cursor-not-allowed disabled:opacity-40 ${
                  periodType === id && !isCustomRange
                    ? "bg-surface dark:bg-surface-dark text-brand dark:text-brand-dim shadow-sm"
                    : "text-ink/50 dark:text-ink-dark/50 hover:text-ink dark:hover:text-ink-dark"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          <button
            type="button"
            onClick={toggleCustomRange}
            className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition ${
              isCustomRange
                ? "bg-brand/10 text-brand dark:text-brand-dim"
                : "text-ink/50 dark:text-ink-dark/50 hover:bg-black/5 dark:hover:bg-white/10"
            }`}
          >
            <CalendarRange size={13} /> Custom range
          </button>

          <button
            onClick={exportPdf}
            disabled={exporting !== null}
            className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs text-ink/50 dark:text-ink-dark/50 hover:bg-black/5 dark:hover:bg-white/10"
          >
            {exporting === "pdf" ? <Loader2 size={13} className="animate-spin" /> : <FileDown size={13} />}
            Export PDF
          </button>
          <button
            onClick={load}
            className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs text-ink/50 dark:text-ink-dark/50 hover:bg-black/5 dark:hover:bg-white/10"
          >
            <RefreshCw size={13} className={loading ? "animate-spin" : ""} /> Refresh
          </button>
        </div>
      </div>

      {error && <p className="rounded-lg bg-red-500/10 px-3 py-2 text-xs text-red-600 dark:text-red-400">{error}</p>}

      {!insights ? (
        <Card className="p-8 text-center text-sm text-ink/50 dark:text-ink-dark/50">Loading...</Card>
      ) : insights.total_items === 0 ? (
        <Card className="p-8 text-center text-sm text-ink/50 dark:text-ink-dark/50">No feedback for this period yet.</Card>
      ) : (
        <>
          {topCategory && (
            <Card className="border-brand/20 bg-brand/[0.06] p-5 dark:bg-brand/[0.1]">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-brand dark:text-brand-dim">Top category this period</p>
              <div className="mt-1.5 flex flex-wrap items-baseline gap-2">
                <h3 className="font-display text-xl font-bold text-ink dark:text-ink-dark">{topCategory.category}</h3>
                <span className="text-sm text-ink/60 dark:text-ink-dark/60">
                  {topCategory.count} mention{topCategory.count === 1 ? "" : "s"} ·{" "}
                  {Math.round((100 * topCategory.count) / insights.total_items)}% of all feedback this period
                </span>
              </div>
            </Card>
          )}

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8">
            <StatTile label="Total feedback" value={insights.total_items} />
            <StatTile label="Positive" value={insights.sentiment_distribution.positive ?? 0} tone="good" />
            <StatTile label="Neutral" value={insights.sentiment_distribution.neutral ?? 0} />
            <StatTile label="Negative" value={insights.sentiment_distribution.negative ?? 0} tone="bad" />
            <StatTile label="Actionable" value={insights.actionable_count} />
            <StatTile label="Avg sentiment" value={`${insights.avg_sentiment_score >= 0 ? "+" : ""}${insights.avg_sentiment_score.toFixed(2)}`} />
            <StatTile label="Avg urgency" value={`${Math.round(insights.avg_urgency_score * 100)}%`} />
            <StatTile
              label="Avg rating"
              value={insights.rated_count > 0 ? `★ ${insights.avg_rating.toFixed(1)}` : "—"}
              sub={insights.rated_count > 0 ? `${insights.rated_count} rated` : "no ratings this period"}
            />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card className="p-5">
              <h3 className="mb-1 text-sm font-semibold">Feedback volume by category</h3>
              <p className="mb-3 text-xs text-ink/50 dark:text-ink-dark/50">Which categories are mentioned most this period — each category keeps its own color everywhere in this app</p>
              <ResponsiveContainer width="100%" height={Math.max(220, categoryVolumeData.length * 30)}>
                <BarChart data={categoryVolumeData} layout="vertical" margin={{ left: 24, right: 24 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} opacity={0.15} />
                  <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
                  <YAxis type="category" dataKey="category" width={170} tick={{ fontSize: 12 }} />
                  <Tooltip contentStyle={{ borderRadius: 12, border: "none", fontSize: 12 }} formatter={(value) => [value, "Feedback items"]} />
                  <Bar dataKey="count" name="Feedback items" radius={[0, 6, 6, 0]} barSize={18}>
                    {categoryVolumeData.map((entry) => (
                      <Cell key={entry.category} fill={categoryColor(entry.category)} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </Card>

            <Card className="p-5">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <h3 className="mb-1 text-sm font-semibold">
                    Themes within {themeCategoryEntry ? `"${themeCategoryEntry.category}"` : "a category"}
                  </h3>
                  <p className="mb-3 text-xs text-ink/50 dark:text-ink-dark/50">
                    {themeCategoryEntry ? "What these mentions are actually about this period" : "No category data for this period"}
                  </p>
                </div>
                {categoryOptionsSorted.length > 0 && (
                  <select
                    value={themeCategoryEntry?.category ?? ""}
                    onChange={(e) => setThemeCategory(e.target.value)}
                    className="rounded-lg border border-black/10 dark:border-white/15 bg-transparent px-2 py-1 text-xs text-ink dark:text-ink-dark"
                  >
                    {categoryOptionsSorted.map((c) => (
                      <option key={c.category} value={c.category}>
                        {c.category}
                      </option>
                    ))}
                  </select>
                )}
              </div>
              {topCategoryThemesData.length === 0 ? (
                <p className="py-10 text-center text-sm text-ink/50 dark:text-ink-dark/50">No theme breakdown available for this category.</p>
              ) : (
                <ResponsiveContainer width="100%" height={Math.max(220, topCategoryThemesData.length * 30)}>
                  <BarChart data={topCategoryThemesData} layout="vertical" margin={{ left: 24, right: 24 }}>
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} opacity={0.15} />
                    <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
                    <YAxis type="category" dataKey="theme" width={170} tick={{ fontSize: 12 }} />
                    <Tooltip contentStyle={{ borderRadius: 12, border: "none", fontSize: 12 }} formatter={(value) => [value, "Feedback items"]} />
                    <Bar dataKey="count" name="Feedback items" fill={categoryColor(themeCategoryEntry?.category)} radius={[0, 6, 6, 0]} barSize={18} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </Card>

            <Card className="p-5">
              <h3 className="mb-1 text-sm font-semibold">Sentiment distribution</h3>
              <p className="mb-3 text-xs text-ink/50 dark:text-ink-dark/50">
                {insights.period_start} – {insights.period_end}
              </p>
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
            </Card>

            {!isCustomRange && (
              <Card className="p-5">
                <h3 className="mb-1 text-sm font-semibold">Sentiment over time</h3>
                <p className="mb-3 text-xs text-ink/50 dark:text-ink-dark/50">
                  Average sentiment across the last {series?.length ?? 0} {periodType} periods
                </p>
                <ResponsiveContainer width="100%" height={240}>
                  <LineChart data={series ?? []} margin={{ left: -16 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.15} />
                    <XAxis dataKey="period_key" tick={{ fontSize: 11 }} />
                    <YAxis domain={[-1, 1]} tick={{ fontSize: 11 }} />
                    <ReferenceLine y={0} stroke="#9a9a9f" strokeDasharray="3 3" />
                    <Tooltip
                      contentStyle={{ borderRadius: 12, border: "none", fontSize: 12 }}
                      formatter={(value) => [Number(value).toFixed(2), "Avg. sentiment"]}
                      labelFormatter={(_, payload) =>
                        payload?.[0]?.payload ? `${payload[0].payload.period_start} – ${payload[0].payload.period_end}` : ""
                      }
                    />
                    <Line type="monotone" dataKey="avg_sentiment_score" name="Avg. sentiment" stroke="#3d6b96" strokeWidth={2} dot={{ r: 3 }} activeDot={{ r: 5 }} />
                  </LineChart>
                </ResponsiveContainer>
              </Card>
            )}

            {!isCustomRange && (
              <Card className="p-5">
                <h3 className="mb-1 text-sm font-semibold">Feedback volume over time</h3>
                <p className="mb-3 text-xs text-ink/50 dark:text-ink-dark/50">
                  Total items received across the last {volumeSeriesData.length} {periodType} periods
                </p>
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={volumeSeriesData} margin={{ left: -16 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.15} />
                    <XAxis dataKey="period_key" tick={{ fontSize: 11 }} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                    <Tooltip
                      contentStyle={{ borderRadius: 12, border: "none", fontSize: 12 }}
                      formatter={(value) => [value, "Feedback items"]}
                      labelFormatter={(_, payload) =>
                        payload?.[0]?.payload ? `${payload[0].payload.period_start} – ${payload[0].payload.period_end}` : ""
                      }
                    />
                    <Bar dataKey="total_items" name="Feedback items" fill="#3d6b96" radius={[6, 6, 0, 0]} barSize={28} />
                  </BarChart>
                </ResponsiveContainer>
              </Card>
            )}

            {!isCustomRange && (
              <Card className="p-5">
                <h3 className="mb-1 text-sm font-semibold">Average rating over time</h3>
                <p className="mb-3 text-xs text-ink/50 dark:text-ink-dark/50">
                  Average survey star rating across the last {series?.length ?? 0} {periodType} periods
                </p>
                <ResponsiveContainer width="100%" height={240}>
                  <LineChart data={ratingSeriesData} margin={{ left: -16 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.15} />
                    <XAxis dataKey="period_key" tick={{ fontSize: 11 }} />
                    <YAxis domain={[0, 5]} tick={{ fontSize: 11 }} />
                    <Tooltip
                      contentStyle={{ borderRadius: 12, border: "none", fontSize: 12 }}
                      formatter={(value) => [value == null ? "No rated surveys" : `${Number(value).toFixed(1)} / 5`, "Avg. rating"]}
                      labelFormatter={(_, payload) =>
                        payload?.[0]?.payload ? `${payload[0].payload.period_start} – ${payload[0].payload.period_end}` : ""
                      }
                    />
                    <Line type="monotone" dataKey="avg_rating" name="Avg. rating" stroke="#b8860b" strokeWidth={2} dot={{ r: 3 }} activeDot={{ r: 5 }} connectNulls={false} />
                  </LineChart>
                </ResponsiveContainer>
              </Card>
            )}

            <Card className="p-5">
              <h3 className="mb-1 text-sm font-semibold">Survey ratings</h3>
              <p className="mb-3 text-xs text-ink/50 dark:text-ink-dark/50">
                {insights.rated_count > 0
                  ? `${insights.rated_count} survey${insights.rated_count === 1 ? "" : "s"} this period · avg ${insights.avg_rating.toFixed(1)} / 5`
                  : "No surveys with a star rating this period"}
              </p>
              {insights.rated_count === 0 ? (
                <p className="py-10 text-center text-sm text-ink/50 dark:text-ink-dark/50">
                  Nothing to show — star ratings only come from the customer survey form, not tickets or imported reviews.
                </p>
              ) : (
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={ratingChartData}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.15} />
                    <XAxis dataKey="label" tick={{ fontSize: 12 }} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                    <Tooltip contentStyle={{ borderRadius: 12, border: "none", fontSize: 12 }} formatter={(value) => [value, "Responses"]} />
                    <Bar dataKey="count" radius={[6, 6, 0, 0]} barSize={36}>
                      {ratingChartData.map((entry) => (
                        <Cell key={entry.star} fill={ratingColor(entry.star)} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
