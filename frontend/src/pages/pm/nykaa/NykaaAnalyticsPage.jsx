import { useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  Treemap,
  XAxis,
  YAxis,
} from "recharts";
import { ArrowLeft, Loader2, RefreshCw, Star } from "lucide-react";
import { api } from "../../../api";
import { Card } from "../../../components/primitives";
import { yearOptions } from "../../../periodNav";

// A full analyst-style dashboard over the PM's raw Nykaa Pulse feedback list
// (nykaaPmFeedback — every review, catalog-joined) rather than the fixed
// brand/category/product breakdown endpoints — computing every aggregate
// here client-side is what makes brand filtering and this many cross-cuts
// of the same data possible without a matching new backend endpoint per chart.
//
// Two views share one dataset: with "All brands" selected this is a
// cross-brand comparison surface (which brands are winning, where the
// volume/complaints are, what analysts need to decide where to focus);
// picking a single brand swaps in that brand's own deep dive (its category/
// subcategory mix, themes, trend, products). There's deliberately no second
// "by category" dropdown — a PM who wants a category slice now reads it
// straight off the category/subcategory ranking chart instead of hiding
// every other category to get it.
//
// Chart-type variety is intentional, not decorative: ranking jobs (top
// brands/categories/themes/teams) stay bar charts because that's the
// correct form for magnitude, but "compare brands to each other" gets
// forms bar/pie can't do well — three line charts tracking the top brands'
// volume and rating over time plus the overall sentiment trend, and a
// diverging bar for each brand's positive-rate delta vs the overall average.
//
// Color choices follow one rule throughout: charts whose job is *ranking/
// magnitude* (top brands, top categories, team ownership, themes) get ONE
// flat hue per chart — coloring every bar a different hue would bury the
// one thing the chart is actually saying. Color is reserved for charts
// where it carries real status meaning: sentiment (good/neutral/bad),
// rating tone, urgency tier, and above/below-average polarity — always the
// same fixed hues the rest of this app already uses for those, never a
// rainbow. The one exception is the multi-brand trend line, where the
// brands genuinely are the subject — that uses this app's fixed-order
// categorical slots (same ordering already validated for the shared
// category palette in AnalyticsPage.jsx), capped at 5 series.
const SENTIMENT_COLORS = { positive: "#2f8f5b", neutral: "#556270", negative: "#c0392b" };
const SENTIMENT_ORDER = ["positive", "neutral", "negative"];
const ratingColor = (r) => (r >= 4 ? "#2f8f5b" : r >= 3 ? "#b8860b" : "#c0392b");
const URGENCY_ORDER = ["High", "Medium", "Low"];
const URGENCY_COLORS = { High: "#c0392b", Medium: "#b8860b", Low: "#2f8f5b" };
function urgencyTier(score) {
  if (score >= 0.6) return "High";
  if (score >= 0.3) return "Medium";
  return "Low";
}

// All four pulled straight from this app's real theme (frontend/src/index.css's
// --color-brand/--color-brand-dim/--color-high/--color-medium/--color-low) —
// no off-theme hues (the old blue/purple/slate here didn't belong to this
// app's actual pink/red/amber/green palette).
const HUE_BRAND = "#d6588c";
const HUE_CATEGORY = "#d6588c";
const HUE_SUBCATEGORY = "#f2a6c6";
const HUE_POSITIVE = "#2f8f5b";
const HUE_NEGATIVE = "#c0392b";
const HUE_NEUTRAL_RANK = "#b8860b";
// Light -> dark steps of the brand hue, for the recurring-themes treemap —
// a magnitude job (more mentions = darker), never a per-cell rainbow.
const PINK_RAMP = ["#f6d5e3", "#eeb3cc", "#e491b5", "#d6588c", "#b83f6c", "#8f2f53"];
// Fixed-order categorical slots 1-5 (blue/orange/aqua/yellow/magenta) — the
// same validated ordering used for this app's category palette — reused
// here for the one chart where brand identity itself is the subject
// (the trend comparison). Capped at 5 lines: past that, adjacent-hue
// confusion sets in and a legend stops being enough.
const BRAND_SERIES_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"];

// Same category -> team convention as the shared ticket-routing table
// (backend models.DEFAULT_TEAM_BY_CATEGORY) — duplicated here as a display
// constant (this page never talks to that Python enum directly) so a PM can
// see which internal team would own the most-mentioned issues.
const TEAM_BY_FEEDBACK_CATEGORY = {
  "Product Quality & Fit": "Product Quality Team",
  "Packaging & Damage": "Product Quality Team",
  "Delivery & Logistics": "Order & Delivery Team",
  "Review & App Flow Friction": "Technical Support Team",
  "Authenticity & Trust": "Product Quality Team",
  "Personalization Mismatch": "Account & Loyalty Team",
  "Pricing & Offers": "Payments & Billing Team",
  "Rewards & Loyalty": "Account & Loyalty Team",
  "Customer Support": "Triage",
};

const tooltipStyle = { borderRadius: 12, border: "none", fontSize: 12 };

function StatTile({ label, value, sub, tone }) {
  const toneClass =
    tone === "good"
      ? "text-emerald-600 dark:text-emerald-400"
      : tone === "bad"
        ? "text-red-600 dark:text-red-400"
        : "text-ink dark:text-ink-dark";
  return (
    <Card className="p-3.5">
      <p className="text-[11px] uppercase tracking-wide text-ink/40 dark:text-ink-dark/40">{label}</p>
      <p className={`mt-1 truncate font-display text-xl font-bold ${toneClass}`}>{value}</p>
      {sub && <p className="mt-0.5 text-[11px] text-ink/40 dark:text-ink-dark/40">{sub}</p>}
    </Card>
  );
}

function SectionHeading({ children }) {
  return (
    <h3 className="font-display text-sm font-semibold uppercase tracking-wide text-ink/50 dark:text-ink-dark/50">
      {children}
    </h3>
  );
}

function ChartCard({ title, sub, headerRight, empty, height = 240, className = "", children }) {
  return (
    <Card className={`p-5 ${className}`}>
      <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">{title}</h3>
        {headerRight}
      </div>
      {sub && <p className="mb-3 text-xs text-ink/50 dark:text-ink-dark/50">{sub}</p>}
      {empty ? (
        <p className="py-10 text-center text-sm text-ink/50 dark:text-ink-dark/50">{empty}</p>
      ) : (
        <ResponsiveContainer width="100%" height={height}>
          {children}
        </ResponsiveContainer>
      )}
    </Card>
  );
}

// A single-hue vertical ranking bar — the shared shape behind every
// "top N by volume" chart (brands, categories, subcategories, teams), so
// they read as one consistent family rather than N differently-styled charts.
function RankBarChart({ data, dataKeyName, color, formatterLabel }) {
  return (
    <BarChart data={data} margin={{ bottom: 16 }}>
      <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.15} />
      <XAxis dataKey={dataKeyName} tick={{ fontSize: 11 }} interval={0} angle={-25} textAnchor="end" height={60} />
      <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
      <Tooltip contentStyle={tooltipStyle} formatter={(value) => [value, formatterLabel]} />
      <Bar dataKey="value" fill={color} radius={[6, 6, 0, 0]} barSize={28} />
    </BarChart>
  );
}

// Whole stars (rounded) for a 0-5 rating — the same glyph vocabulary a
// layman already knows from every shopping app, so a bar's value reads
// instantly without needing to interpret the Y-axis scale at all. Whole
// stars only (no half-star glyph) since that character renders
// inconsistently across fonts — the exact decimal is spelled out alongside.
function starGlyphs(value) {
  const full = Math.round(Math.max(0, Math.min(5, value)));
  return "★".repeat(full) + "☆".repeat(5 - full);
}

// Compact star + number sitting directly above each bar (skipped for months
// a brand has no rated reviews — LabelList only calls this for bars that
// actually rendered, so nulls never show a bogus "★0.0").
function StarBarLabel({ x, y, width, value }) {
  if (value == null) return null;
  return (
    <text x={x + width / 2} y={y - 4} textAnchor="middle" fontSize={9} fontWeight={700} fill="#b8860b">
      {`★ ${Number(value).toFixed(1)}`}
    </text>
  );
}

export function NykaaAnalyticsPage() {
  const [items, setItems] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [brandFilter, setBrandFilter] = useState("all");
  // Which brand the "Themes within <brand>" chart on the overview is
  // currently showing — independent of brandFilter (the full-page drill-
  // down), so a PM can flip through brands' themes without leaving the
  // overview. Defaults to the top brand by volume once data loads.
  const [themesBrand, setThemesBrand] = useState(null);
  // Which year the "Brand rating trend" chart below is scoped to.
  const [ratingYear, setRatingYear] = useState(() => new Date().getFullYear());
  const ratingYearOptions = useMemo(() => yearOptions(), []);
  // A second-level filter, only meaningful once a brand is picked — lets a
  // PM drill from "this brand" down to "this brand's Skincare mentions"
  // without ever hiding the rest of the brand's categories (see
  // brandCategoryOptions below, which always lists every category the
  // *unfiltered* brand has, so switching categories is a toggle, not a
  // one-way trip).
  const [categoryFilter, setCategoryFilter] = useState("all");

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const r = await api.nykaaPmFeedback();
      setItems(r.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const brandOptions = useMemo(() => (items ? [...new Set(items.map((i) => i.brand).filter(Boolean))].sort() : []), [items]);

  const isOverview = brandFilter === "all";

  // Reset the category drill-down whenever the brand changes (including
  // back to "All brands") — a category filter from the last brand has no
  // meaning for a different one.
  useEffect(() => {
    setCategoryFilter("all");
  }, [brandFilter]);

  const brandScopedItems = useMemo(() => {
    if (!items) return [];
    return isOverview ? items : items.filter((i) => i.brand === brandFilter);
  }, [items, brandFilter, isOverview]);

  const filtered = useMemo(() => {
    if (isOverview || categoryFilter === "all") return brandScopedItems;
    return brandScopedItems.filter((i) => i.catalog_category === categoryFilter);
  }, [brandScopedItems, isOverview, categoryFilter]);

  // Every category this brand has, independent of the category filter
  // itself — the picker's own option list, so selecting one never removes
  // the others from view.
  const brandCategoryOptions = useMemo(() => {
    const map = new Map();
    for (const i of brandScopedItems) {
      if (!i.catalog_category) continue;
      map.set(i.catalog_category, (map.get(i.catalog_category) ?? 0) + 1);
    }
    return [...map.entries()].map(([category, count]) => ({ category, count })).sort((a, b) => b.count - a.count);
  }, [brandScopedItems]);
  const brandCategoryChartData = brandCategoryOptions.map((c) => ({ category: c.category, value: c.count }));

  const stats = useMemo(() => {
    const sentiment = { positive: 0, neutral: 0, negative: 0 };
    let ratedSum = 0;
    let ratedCount = 0;
    let actionable = 0;
    let urgencySum = 0;
    for (const i of filtered) {
      if (i.sentiment_label in sentiment) sentiment[i.sentiment_label] += 1;
      if (i.rating) {
        ratedSum += i.rating;
        ratedCount += 1;
      }
      if (i.is_actionable_ticket) actionable += 1;
      urgencySum += i.urgency_score ?? 0;
    }
    return {
      total: filtered.length,
      sentiment,
      avgRating: ratedCount > 0 ? ratedSum / ratedCount : null,
      ratedCount,
      actionable,
      avgUrgency: filtered.length > 0 ? urgencySum / filtered.length : 0,
    };
  }, [filtered]);

  // Only meaningful across all brands — this is the input to every
  // brand-vs-brand chart on the overview (table, trend lines, diverging bar).
  const brandAgg = useMemo(() => {
    const map = new Map();
    for (const i of items ?? []) {
      if (!i.brand) continue;
      if (!map.has(i.brand)) map.set(i.brand, { brand: i.brand, count: 0, positive: 0, ratedSum: 0, ratedCount: 0, categories: new Map(), themes: new Map() });
      const b = map.get(i.brand);
      b.count += 1;
      if (i.sentiment_label === "positive") b.positive += 1;
      if (i.rating) {
        b.ratedSum += i.rating;
        b.ratedCount += 1;
      }
      if (i.catalog_category) b.categories.set(i.catalog_category, (b.categories.get(i.catalog_category) ?? 0) + 1);
      if (i.theme) b.themes.set(i.theme, (b.themes.get(i.theme) ?? 0) + 1);
    }
    const topOf = (m) => {
      let best = null;
      let bestCount = 0;
      for (const [k, v] of m) {
        if (v > bestCount) {
          best = k;
          bestCount = v;
        }
      }
      return best;
    };
    return [...map.values()].map((b) => ({
      brand: b.brand,
      count: b.count,
      positiveRate: b.count > 0 ? Math.round((100 * b.positive) / b.count) : 0,
      avgRating: b.ratedCount > 0 ? b.ratedSum / b.ratedCount : null,
      ratedCount: b.ratedCount,
      topCategory: topOf(b.categories) ?? "—",
      topTheme: topOf(b.themes) ?? "—",
    }));
  }, [items]);

  const topBrandsByVolume = useMemo(
    () => [...brandAgg].sort((a, b) => b.count - a.count).slice(0, 8),
    [brandAgg],
  );

  // Default the "Themes within <brand>" picker to the top brand by volume
  // once data loads, and keep it valid if the top brand ever changes.
  useEffect(() => {
    if (topBrandsByVolume.length === 0) return;
    if (!themesBrand || !topBrandsByVolume.some((b) => b.brand === themesBrand)) {
      setThemesBrand(topBrandsByVolume[0].brand);
    }
  }, [topBrandsByVolume, themesBrand]);

  const themesForSelectedBrand = useMemo(() => {
    if (!themesBrand) return [];
    return aggregateThemes((items ?? []).filter((i) => i.brand === themesBrand));
  }, [items, themesBrand]);

  const top5BrandNames = useMemo(() => topBrandsByVolume.slice(0, 5).map((b) => b.brand), [topBrandsByVolume]);
  const multiBrandTrendData = useMemo(() => {
    if (top5BrandNames.length === 0) return [];
    const map = new Map();
    for (const i of items ?? []) {
      if (!i.created_at || !top5BrandNames.includes(i.brand)) continue;
      const key = i.created_at.slice(0, 7); // YYYY-MM
      if (!map.has(key)) {
        const row = { period: key };
        for (const b of top5BrandNames) row[b] = 0;
        map.set(key, row);
      }
      map.get(key)[i.brand] += 1;
    }
    return [...map.values()]
      .sort((a, b) => a.period.localeCompare(b.period))
      .map((row) => ({ ...row, label: new Date(`${row.period}-01`).toLocaleDateString(undefined, { month: "short", year: "2-digit" }) }));
  }, [items, top5BrandNames]);

  // Per-brand average rating for a single selected year (see the year
  // picker on the chart itself) — brand is the X-axis category now, not a
  // time period, so there's no per-brand color legend to keep small; every
  // bar is colored by its own rating tone instead (see ratingColor below,
  // same convention as the Products comparison chart).
  const brandRatingByYear = useMemo(() => {
    const map = new Map();
    for (const i of items ?? []) {
      if (!i.created_at || !i.rating || !i.brand) continue;
      if (new Date(i.created_at).getFullYear() !== ratingYear) continue;
      if (!map.has(i.brand)) map.set(i.brand, { sum: 0, count: 0 });
      const cell = map.get(i.brand);
      cell.sum += i.rating;
      cell.count += 1;
    }
    return [...map.entries()]
      .map(([brand, { sum, count }]) => ({ brand, value: Number((sum / count).toFixed(2)), count }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 10);
  }, [items, ratingYear]);

  // Overall sentiment score across every brand, month over month — a single
  // line (no brand identity to encode) alongside the two per-brand lines above.
  const overallSentimentTrendData = useMemo(() => {
    const map = new Map();
    for (const i of filtered) {
      if (!i.created_at || i.sentiment_score == null) continue;
      const key = i.created_at.slice(0, 7);
      if (!map.has(key)) map.set(key, { sum: 0, count: 0 });
      const cell = map.get(key);
      cell.sum += i.sentiment_score;
      cell.count += 1;
    }
    return [...map.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([period, { sum, count }]) => ({
        period,
        label: new Date(`${period}-01`).toLocaleDateString(undefined, { month: "short", year: "2-digit" }),
        avg_sentiment: Number((sum / count).toFixed(2)),
      }));
  }, [filtered]);

  // Category/subcategory ranking is scoped to whatever's currently
  // filtered — across all brands on the overview, or within one brand once
  // it's selected. This is the replacement for the old "by category"
  // dropdown: instead of hiding every other category to see one, the full
  // ranked breakdown is always on screen.
  const categoryAgg = useMemo(() => {
    const map = new Map();
    for (const i of filtered) {
      if (!i.catalog_category) continue;
      map.set(i.catalog_category, (map.get(i.catalog_category) ?? 0) + 1);
    }
    return [...map.entries()].map(([category, value]) => ({ category, value })).sort((a, b) => b.value - a.value);
  }, [filtered]);
  const topCategoriesByVolume = categoryAgg.slice(0, 8);

  const subcategoryAgg = useMemo(() => {
    const map = new Map();
    for (const i of filtered) {
      if (!i.catalog_subcategory) continue;
      map.set(i.catalog_subcategory, (map.get(i.catalog_subcategory) ?? 0) + 1);
    }
    return [...map.entries()].map(([subcategory, value]) => ({ subcategory, value })).sort((a, b) => b.value - a.value);
  }, [filtered]);
  const topSubcategoriesByVolume = subcategoryAgg.slice(0, 8);

  function aggregateThemes(rows) {
    const map = new Map();
    for (const i of rows) {
      if (!i.theme) continue;
      map.set(i.theme, (map.get(i.theme) ?? 0) + 1);
    }
    return [...map.entries()]
      .map(([theme, value]) => ({ theme, value }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 5);
  }
  const positiveThemes = useMemo(() => aggregateThemes(filtered.filter((i) => i.sentiment_label === "positive")), [filtered]);
  const negativeThemes = useMemo(() => aggregateThemes(filtered.filter((i) => i.sentiment_label === "negative")), [filtered]);
  const recurringThemes = useMemo(() => {
    const ranked = aggregateThemes(filtered);
    return ranked.map((t, i) => ({ name: t.theme, size: t.value, fill: PINK_RAMP[Math.min(i, PINK_RAMP.length - 1)] }));
  }, [filtered]);

  // Single-series trend — only rendered on the brand-detail view; the
  // overview uses the multi-brand comparison line instead.
  const trendData = useMemo(() => {
    const map = new Map();
    for (const i of filtered) {
      if (!i.created_at) continue;
      const key = i.created_at.slice(0, 7);
      map.set(key, (map.get(key) ?? 0) + 1);
    }
    return [...map.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([period, count]) => ({
        period,
        count,
        label: new Date(`${period}-01`).toLocaleDateString(undefined, { month: "short", year: "2-digit" }),
      }));
  }, [filtered]);

  const severityData = useMemo(() => {
    const counts = { High: 0, Medium: 0, Low: 0 };
    for (const i of filtered) counts[urgencyTier(i.urgency_score ?? 0)] += 1;
    return URGENCY_ORDER.map((k) => ({ name: k, value: counts[k] }));
  }, [filtered]);

  const teamData = useMemo(() => {
    const map = new Map();
    for (const i of filtered) {
      const team = TEAM_BY_FEEDBACK_CATEGORY[i.category] ?? "Triage";
      map.set(team, (map.get(team) ?? 0) + 1);
    }
    return [...map.entries()].map(([team, value]) => ({ team, value })).sort((a, b) => b.value - a.value);
  }, [filtered]);

  // Only rendered on the brand-detail view — comparing products across
  // every brand at once isn't a meaningful cut, but it is within one brand.
  const productAgg = useMemo(() => {
    const map = new Map();
    for (const i of filtered) {
      if (!i.product_name) continue;
      if (!map.has(i.product_name)) map.set(i.product_name, { name: i.product_name, count: 0, ratedSum: 0, ratedCount: 0 });
      const p = map.get(i.product_name);
      p.count += 1;
      if (i.rating) {
        p.ratedSum += i.rating;
        p.ratedCount += 1;
      }
    }
    return [...map.values()]
      .map((p) => ({ ...p, avgRating: p.ratedCount > 0 ? p.ratedSum / p.ratedCount : null }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 8);
  }, [filtered]);

  const ratingDistData = useMemo(
    () => [1, 2, 3, 4, 5].map((star) => ({ star, label: `${star}★`, value: filtered.filter((i) => i.rating === star).length })),
    [filtered],
  );

  const sentimentDonutData = SENTIMENT_ORDER.map((k) => ({ name: k, value: stats.sentiment[k] }));

  const recentReviews = useMemo(
    () => [...filtered].sort((a, b) => new Date(b.created_at) - new Date(a.created_at)).slice(0, 8),
    [filtered],
  );

  const topBrand = topBrandsByVolume[0] ?? null;
  const topCategory = categoryAgg[0] ?? null;
  const selectedBrandAgg = isOverview ? null : brandAgg.find((b) => b.brand === brandFilter) ?? null;

  const isLoaded = Boolean(items);
  const isEmpty = isLoaded && filtered.length === 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-display text-lg font-semibold">Analytics</h2>
          <p className="mt-1 text-sm text-ink/60 dark:text-ink-dark/60">
            {isOverview
              ? "Every Nykaa Pulse review across all brands — compare brands, then filter to one for its full breakdown."
              : `Deep dive on ${brandFilter} — every review for this brand.`}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {!isOverview && (
            <button
              onClick={() => setBrandFilter("all")}
              className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-xs font-medium text-brand hover:bg-brand/10 dark:text-brand-dim"
            >
              <ArrowLeft size={13} /> All brands
            </button>
          )}
          <select
            value={brandFilter}
            onChange={(e) => setBrandFilter(e.target.value)}
            className="rounded-lg border border-black/10 dark:border-white/15 bg-transparent px-2.5 py-1.5 text-xs text-ink dark:text-ink-dark"
          >
            <option value="all">All brands</option>
            {brandOptions.map((b) => (
              <option key={b} value={b}>
                {b}
              </option>
            ))}
          </select>
          <button
            onClick={load}
            className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs text-ink/50 dark:text-ink-dark/50 hover:bg-black/5 dark:hover:bg-white/10"
          >
            <RefreshCw size={13} className={loading ? "animate-spin" : ""} /> Refresh
          </button>
        </div>
      </div>

      {error && <p className="rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-600 dark:text-red-400">{error}</p>}

      {!isLoaded ? (
        <Card className="p-8 text-center text-sm text-ink/50 dark:text-ink-dark/50">
          <span className="inline-flex items-center gap-2">
            <Loader2 size={16} className="animate-spin" /> Loading...
          </span>
        </Card>
      ) : isEmpty ? (
        <Card className="p-8 text-center text-sm text-ink/50 dark:text-ink-dark/50">No feedback matches this filter yet.</Card>
      ) : (
        <>
          {!isOverview && selectedBrandAgg && (
            <Card className="border-brand/20 bg-brand/[0.06] p-5 dark:bg-brand/[0.1]">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-brand dark:text-brand-dim">Brand snapshot</p>
              <div className="mt-1.5 flex flex-wrap items-baseline gap-2">
                <h3 className="font-display text-xl font-bold text-ink dark:text-ink-dark">{brandFilter}</h3>
                <span className="text-sm text-ink/60 dark:text-ink-dark/60">
                  {selectedBrandAgg.count} review{selectedBrandAgg.count === 1 ? "" : "s"} ·{" "}
                  {selectedBrandAgg.avgRating != null ? `★ ${selectedBrandAgg.avgRating.toFixed(1)} avg` : "no ratings yet"} ·{" "}
                  {selectedBrandAgg.positiveRate}% positive · top category: {selectedBrandAgg.topCategory}
                </span>
              </div>
            </Card>
          )}

          {!isOverview && brandCategoryOptions.length > 0 && (
            <Card className="p-4">
              <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-ink/40 dark:text-ink-dark/40">
                Filter {brandFilter}'s data by category
              </p>
              <div className="flex flex-wrap gap-1.5">
                <button
                  onClick={() => setCategoryFilter("all")}
                  className={`rounded-full px-3 py-1.5 text-xs font-medium transition ${
                    categoryFilter === "all"
                      ? "bg-brand text-white"
                      : "bg-black/5 dark:bg-white/10 text-ink/60 dark:text-ink-dark/60 hover:bg-black/10 dark:hover:bg-white/15"
                  }`}
                >
                  All categories
                </button>
                {brandCategoryOptions.map((c) => (
                  <button
                    key={c.category}
                    onClick={() => setCategoryFilter(c.category)}
                    className={`rounded-full px-3 py-1.5 text-xs font-medium transition ${
                      categoryFilter === c.category
                        ? "bg-brand text-white"
                        : "bg-black/5 dark:bg-white/10 text-ink/60 dark:text-ink-dark/60 hover:bg-black/10 dark:hover:bg-white/15"
                    }`}
                  >
                    {c.category} <span className="opacity-60">({c.count})</span>
                  </button>
                ))}
              </div>
              {categoryFilter !== "all" && (
                <p className="mt-2 text-xs text-ink/50 dark:text-ink-dark/50">
                  Showing every chart below scoped to {brandFilter} · {categoryFilter} only ({filtered.length} review
                  {filtered.length === 1 ? "" : "s"}).
                </p>
              )}
            </Card>
          )}

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
            <StatTile label="Total feedback" value={stats.total.toLocaleString()} />
            <StatTile label="Positive" value={stats.sentiment.positive} tone="good" />
            <StatTile label="Neutral" value={stats.sentiment.neutral} />
            <StatTile label="Negative" value={stats.sentiment.negative} tone="bad" />
            <StatTile
              label="Avg rating"
              value={stats.avgRating != null ? `★ ${stats.avgRating.toFixed(1)}` : "—"}
              sub={stats.ratedCount > 0 ? `${stats.ratedCount} rated` : "no ratings yet"}
            />
            <StatTile label="Needs follow-up" value={stats.actionable} sub={`${Math.round(stats.avgUrgency * 100)}% avg urgency`} />
            {isOverview ? (
              <StatTile
                label="Top brand"
                value={topBrand?.brand ?? "—"}
                sub={topBrand ? `${topBrand.count} reviews · top category: ${topCategory?.category ?? "—"}` : undefined}
              />
            ) : (
              <StatTile label="Top theme" value={selectedBrandAgg?.topTheme ?? "—"} sub="Most-mentioned theme for this brand" />
            )}
          </div>

          {isOverview && (
            <div className="space-y-6">
              <SectionHeading>Brand performance</SectionHeading>

              <div className="grid gap-6 lg:grid-cols-2">
                <ChartCard
                  title="Feedback volume by brand"
                  sub="Most-reviewed brands overall — click a bar's brand in the picker on the right for its themes, or use the brand dropdown above for the full deep dive"
                  empty={topBrandsByVolume.length === 0 ? "No brand data yet." : null}
                  height={280}
                >
                  <RankBarChart data={topBrandsByVolume.map((b) => ({ brand: b.brand, value: b.count }))} dataKeyName="brand" color={HUE_BRAND} formatterLabel="Reviews" />
                </ChartCard>

                <ChartCard
                  title={`Themes within ${themesBrand ?? "—"}`}
                  sub="What this brand's reviews are actually about — top 5 themes"
                  empty={themesForSelectedBrand.length === 0 ? "No themes recorded for this brand yet." : null}
                  height={280}
                  headerRight={
                    topBrandsByVolume.length > 0 && (
                      <select
                        value={themesBrand ?? ""}
                        onChange={(e) => setThemesBrand(e.target.value)}
                        className="rounded-lg border border-black/10 dark:border-white/15 bg-transparent px-2 py-1 text-xs text-ink dark:text-ink-dark"
                      >
                        {topBrandsByVolume.map((b) => (
                          <option key={b.brand} value={b.brand}>
                            {b.brand}
                          </option>
                        ))}
                      </select>
                    )
                  }
                >
                  <BarChart data={themesForSelectedBrand} margin={{ bottom: 16 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.15} />
                    <XAxis dataKey="theme" tick={{ fontSize: 11 }} interval={0} angle={-25} textAnchor="end" height={60} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                    <Tooltip contentStyle={tooltipStyle} formatter={(value) => [value, "Mentions"]} />
                    <Bar dataKey="value" fill={HUE_SUBCATEGORY} radius={[6, 6, 0, 0]} barSize={28} />
                  </BarChart>
                </ChartCard>
              </div>

              <div className="grid gap-6 lg:grid-cols-2">
                <ChartCard
                  title="Brand review trend"
                  sub="Monthly review volume for the top 5 brands by volume"
                  className="lg:col-span-2"
                  empty={multiBrandTrendData.length === 0 ? "No review history yet." : null}
                  height={280}
                >
                  <LineChart data={multiBrandTrendData} margin={{ left: -16 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.15} />
                    <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                    <Tooltip contentStyle={tooltipStyle} />
                    <Legend verticalAlign="bottom" height={28} wrapperStyle={{ fontSize: 11 }} />
                    {top5BrandNames.map((b, idx) => (
                      <Line key={b} type="monotone" dataKey={b} name={b} stroke={BRAND_SERIES_COLORS[idx]} strokeWidth={2} dot={{ r: 3 }} activeDot={{ r: 5 }} />
                    ))}
                  </LineChart>
                </ChartCard>

                <ChartCard
                  title="Brand rating trend"
                  sub={`Average star rating per brand in ${ratingYear} — read straight off the ★ labels, no axis-reading needed.`}
                  className="lg:col-span-2"
                  empty={brandRatingByYear.length === 0 ? `No rated reviews in ${ratingYear} yet.` : null}
                  height={300}
                  headerRight={
                    <select
                      value={ratingYear}
                      onChange={(e) => setRatingYear(Number(e.target.value))}
                      className="rounded-lg border border-black/10 dark:border-white/15 bg-transparent px-2 py-1 text-xs text-ink dark:text-ink-dark"
                    >
                      {ratingYearOptions.map((y) => (
                        <option key={y} value={y}>
                          {y}
                        </option>
                      ))}
                    </select>
                  }
                >
                  <BarChart data={brandRatingByYear} margin={{ left: -16, top: 16, bottom: 16 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.15} />
                    <XAxis dataKey="brand" tick={{ fontSize: 11 }} interval={0} angle={-20} textAnchor="end" height={55} />
                    <YAxis domain={[0, 5]} allowDecimals={false} tick={{ fontSize: 11 }} tickFormatter={(v) => "★".repeat(Math.max(0, Math.round(v)))} />
                    <Tooltip contentStyle={tooltipStyle} formatter={(value) => [`${starGlyphs(value)} (${Number(value).toFixed(1)}/5)`, "Avg rating"]} />
                    <Bar dataKey="value" radius={[4, 4, 0, 0]} barSize={32}>
                      <LabelList dataKey="value" content={<StarBarLabel />} />
                      {brandRatingByYear.map((entry) => (
                        <Cell key={entry.brand} fill={ratingColor(entry.value)} />
                      ))}
                    </Bar>
                  </BarChart>
                </ChartCard>

                <ChartCard
                  title="Overall sentiment trend"
                  sub="Average sentiment score across every brand, month over month"
                  className="lg:col-span-2"
                  empty={overallSentimentTrendData.length === 0 ? "No review history yet." : null}
                  height={240}
                >
                  <LineChart data={overallSentimentTrendData} margin={{ left: -16 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.15} />
                    <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                    <YAxis domain={[-1, 1]} tick={{ fontSize: 11 }} />
                    <ReferenceLine y={0} stroke="#9a9a9f" strokeDasharray="3 3" />
                    <Tooltip contentStyle={tooltipStyle} formatter={(value) => [value, "Avg. sentiment"]} />
                    <Line type="linear" dataKey="avg_sentiment" name="Avg. sentiment" stroke={HUE_CATEGORY} strokeWidth={2} dot={{ r: 3 }} activeDot={{ r: 5 }} />
                  </LineChart>
                </ChartCard>
              </div>

              <SectionHeading>Categories & themes</SectionHeading>
              <div className="grid gap-6 lg:grid-cols-2">
                <ChartCard
                  title="Top categories by volume"
                  sub="Most-reviewed catalog categories across all brands"
                  empty={topCategoriesByVolume.length === 0 ? "No category data yet." : null}
                  height={280}
                >
                  <RankBarChart data={topCategoriesByVolume} dataKeyName="category" color={HUE_CATEGORY} formatterLabel="Reviews" />
                </ChartCard>

                <ChartCard
                  title="Top subcategories by volume"
                  sub="Most-reviewed catalog subcategories across all brands"
                  empty={topSubcategoriesByVolume.length === 0 ? "No subcategory data yet." : null}
                  height={280}
                >
                  <RankBarChart data={topSubcategoriesByVolume} dataKeyName="subcategory" color={HUE_SUBCATEGORY} formatterLabel="Reviews" />
                </ChartCard>

                <ChartCard
                  title="Top positive themes"
                  sub="What reviews praise most often"
                  empty={positiveThemes.length === 0 ? "No positive reviews yet." : null}
                  height={260}
                >
                  <BarChart data={positiveThemes} margin={{ bottom: 16 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.15} />
                    <XAxis dataKey="theme" tick={{ fontSize: 11 }} interval={0} angle={-25} textAnchor="end" height={60} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                    <Tooltip contentStyle={tooltipStyle} formatter={(value) => [value, "Mentions"]} />
                    <Bar dataKey="value" fill={HUE_POSITIVE} radius={[6, 6, 0, 0]} barSize={28} />
                  </BarChart>
                </ChartCard>

                <ChartCard
                  title="Top negative themes"
                  sub="What reviews complain about most often"
                  empty={negativeThemes.length === 0 ? "No negative reviews yet." : null}
                  height={260}
                >
                  <BarChart data={negativeThemes} margin={{ bottom: 16 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.15} />
                    <XAxis dataKey="theme" tick={{ fontSize: 11 }} interval={0} angle={-25} textAnchor="end" height={60} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                    <Tooltip contentStyle={tooltipStyle} formatter={(value) => [value, "Mentions"]} />
                    <Bar dataKey="value" fill={HUE_NEGATIVE} radius={[6, 6, 0, 0]} barSize={28} />
                  </BarChart>
                </ChartCard>

                <ChartCard
                  title="Recurring themes"
                  sub="Every theme mentioned, sized and shaded by how often — darker means more mentions"
                  className="lg:col-span-2"
                  empty={recurringThemes.length === 0 ? "No themes recorded yet." : null}
                  height={260}
                >
                  <Treemap data={recurringThemes} dataKey="size" stroke="#fff" content={<TreemapCell />} />
                </ChartCard>
              </div>

              <SectionHeading>Ratings & sentiment</SectionHeading>
              <div className="grid gap-6 lg:grid-cols-2">
                <ChartCard title="Rating distribution" sub="Every star rating left across these reviews">
                  <BarChart data={ratingDistData}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.15} />
                    <XAxis dataKey="label" tick={{ fontSize: 12 }} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                    <Tooltip contentStyle={tooltipStyle} formatter={(value) => [value, "Reviews"]} />
                    <Bar dataKey="value" radius={[6, 6, 0, 0]} barSize={36}>
                      {ratingDistData.map((entry) => (
                        <Cell key={entry.star} fill={ratingColor(entry.star)} />
                      ))}
                    </Bar>
                  </BarChart>
                </ChartCard>

                <ChartCard title="Sentiment donut" sub={`${stats.total} reviews, split by tone`}>
                  <PieChart>
                    <Pie data={sentimentDonutData} dataKey="value" nameKey="name" innerRadius={50} outerRadius={85} paddingAngle={2}>
                      {sentimentDonutData.map((entry) => (
                        <Cell key={entry.name} fill={SENTIMENT_COLORS[entry.name] ?? "#556270"} />
                      ))}
                    </Pie>
                    <Legend verticalAlign="bottom" height={24} wrapperStyle={{ fontSize: 11, textTransform: "capitalize" }} />
                    <Tooltip contentStyle={tooltipStyle} />
                  </PieChart>
                </ChartCard>
              </div>

              <SectionHeading>Operations</SectionHeading>
              <div className="grid gap-6 lg:grid-cols-2">
                <ChartCard title="Issue severity" sub="Reviews bucketed by urgency score" empty={filtered.length === 0 ? "No data yet." : null} height={220}>
                  <BarChart data={severityData}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.15} />
                    <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                    <Tooltip contentStyle={tooltipStyle} formatter={(value) => [value, "Reviews"]} />
                    <Bar dataKey="value" radius={[6, 6, 0, 0]} barSize={64}>
                      {severityData.map((entry) => (
                        <Cell key={entry.name} fill={URGENCY_COLORS[entry.name]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ChartCard>

                <ChartCard
                  title="Team ownership"
                  sub="Which team would own the most-mentioned issues"
                  empty={teamData.every((t) => t.value === 0) ? "No data yet." : null}
                  height={280}
                >
                  <RankBarChart data={teamData} dataKeyName="team" color={HUE_NEUTRAL_RANK} formatterLabel="Reviews" />
                </ChartCard>
              </div>
            </div>
          )}

          {!isOverview && (
            <div className="space-y-6">
              <SectionHeading>{brandFilter} — category & product mix</SectionHeading>
              <div className="grid gap-6 lg:grid-cols-2">
                <ChartCard
                  title="Categories within this brand"
                  sub="Every category this brand has — click a pill above to filter, unaffected by it here"
                  empty={brandCategoryChartData.length === 0 ? "No category data yet." : null}
                  height={280}
                >
                  <RankBarChart data={brandCategoryChartData} dataKeyName="category" color={HUE_CATEGORY} formatterLabel="Reviews" />
                </ChartCard>

                <ChartCard
                  title="Subcategories within this brand"
                  sub={categoryFilter === "all" ? "A finer cut of the same reviews" : `A finer cut within ${categoryFilter}`}
                  empty={topSubcategoriesByVolume.length === 0 ? "No subcategory data yet." : null}
                  height={280}
                >
                  <RankBarChart data={topSubcategoriesByVolume} dataKeyName="subcategory" color={HUE_SUBCATEGORY} formatterLabel="Reviews" />
                </ChartCard>

                <ChartCard
                  title="Products comparison"
                  sub="Most-reviewed products for this brand — bar color shows average rating tone"
                  className="lg:col-span-2"
                  empty={productAgg.length === 0 ? "No product data yet." : null}
                  height={300}
                >
                  <BarChart data={productAgg} margin={{ bottom: 40 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.15} />
                    <XAxis dataKey="name" tick={{ fontSize: 11 }} interval={0} angle={-30} textAnchor="end" height={80} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                    <Tooltip
                      contentStyle={tooltipStyle}
                      formatter={(value, _n, p) => [value, p.payload.avgRating != null ? `Reviews (★ ${p.payload.avgRating.toFixed(1)})` : "Reviews"]}
                    />
                    <Bar dataKey="count" radius={[6, 6, 0, 0]} barSize={28}>
                      {productAgg.map((entry) => (
                        <Cell key={entry.name} fill={entry.avgRating != null ? ratingColor(entry.avgRating) : "#9a9a9f"} />
                      ))}
                    </Bar>
                  </BarChart>
                </ChartCard>
              </div>

              <SectionHeading>{brandFilter} — themes</SectionHeading>
              <div className="grid gap-6 lg:grid-cols-2">
                <ChartCard
                  title="Top positive themes"
                  sub="What reviews praise most often about this brand"
                  empty={positiveThemes.length === 0 ? "No positive reviews yet." : null}
                  height={260}
                >
                  <BarChart data={positiveThemes} margin={{ bottom: 16 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.15} />
                    <XAxis dataKey="theme" tick={{ fontSize: 11 }} interval={0} angle={-25} textAnchor="end" height={60} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                    <Tooltip contentStyle={tooltipStyle} formatter={(value) => [value, "Mentions"]} />
                    <Bar dataKey="value" fill={HUE_POSITIVE} radius={[6, 6, 0, 0]} barSize={28} />
                  </BarChart>
                </ChartCard>

                <ChartCard
                  title="Top negative themes"
                  sub="What reviews complain about most often about this brand"
                  empty={negativeThemes.length === 0 ? "No negative reviews yet." : null}
                  height={260}
                >
                  <BarChart data={negativeThemes} margin={{ bottom: 16 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.15} />
                    <XAxis dataKey="theme" tick={{ fontSize: 11 }} interval={0} angle={-25} textAnchor="end" height={60} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                    <Tooltip contentStyle={tooltipStyle} formatter={(value) => [value, "Mentions"]} />
                    <Bar dataKey="value" fill={HUE_NEGATIVE} radius={[6, 6, 0, 0]} barSize={28} />
                  </BarChart>
                </ChartCard>

                <ChartCard
                  title="Recurring themes"
                  sub="Every theme mentioned for this brand, sized and shaded by how often"
                  className="lg:col-span-2"
                  empty={recurringThemes.length === 0 ? "No themes recorded yet." : null}
                  height={240}
                >
                  <Treemap data={recurringThemes} dataKey="size" stroke="#fff" content={<TreemapCell />} />
                </ChartCard>
              </div>

              <SectionHeading>{brandFilter} — ratings, sentiment & trend</SectionHeading>
              <div className="grid gap-6 lg:grid-cols-2">
                <ChartCard title="Rating distribution" sub="Every star rating left for this brand">
                  <BarChart data={ratingDistData}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.15} />
                    <XAxis dataKey="label" tick={{ fontSize: 12 }} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                    <Tooltip contentStyle={tooltipStyle} formatter={(value) => [value, "Reviews"]} />
                    <Bar dataKey="value" radius={[6, 6, 0, 0]} barSize={36}>
                      {ratingDistData.map((entry) => (
                        <Cell key={entry.star} fill={ratingColor(entry.star)} />
                      ))}
                    </Bar>
                  </BarChart>
                </ChartCard>

                <ChartCard title="Sentiment donut" sub={`${stats.total} reviews, split by tone`}>
                  <PieChart>
                    <Pie data={sentimentDonutData} dataKey="value" nameKey="name" innerRadius={50} outerRadius={85} paddingAngle={2}>
                      {sentimentDonutData.map((entry) => (
                        <Cell key={entry.name} fill={SENTIMENT_COLORS[entry.name] ?? "#556270"} />
                      ))}
                    </Pie>
                    <Legend verticalAlign="bottom" height={24} wrapperStyle={{ fontSize: 11, textTransform: "capitalize" }} />
                    <Tooltip contentStyle={tooltipStyle} />
                  </PieChart>
                </ChartCard>

                <ChartCard
                  title="Feedback trend"
                  sub="Review volume over time for this brand"
                  className="lg:col-span-2"
                  empty={trendData.length === 0 ? "No review history yet." : null}
                  height={240}
                >
                  <AreaChart data={trendData} margin={{ left: -16 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.15} />
                    <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                    <Tooltip contentStyle={tooltipStyle} formatter={(value) => [value, "Reviews"]} />
                    <Area type="linear" dataKey="count" name="Reviews" stroke={HUE_BRAND} fill={HUE_BRAND} fillOpacity={0.18} strokeWidth={2} />
                  </AreaChart>
                </ChartCard>
              </div>
            </div>
          )}

          <Card className="p-5">
            <h3 className="mb-1 text-sm font-semibold">Recent reviews</h3>
            <p className="mb-3 text-xs text-ink/50 dark:text-ink-dark/50">The latest {recentReviews.length} reviews in this slice</p>
            <div className="thin-scroll max-h-[420px] space-y-2 overflow-y-auto pr-1">
              {recentReviews.map((r) => (
                <div key={r.source_ref} className="rounded-xl border border-black/8 dark:border-white/10 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-ink dark:text-ink-dark">{r.product_name}</p>
                      <p className="text-[11px] text-ink/40 dark:text-ink-dark/40">
                        {r.brand} · {r.catalog_category} · {new Date(r.created_at).toLocaleDateString()}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      {r.rating && (
                        <span className="inline-flex items-center gap-0.5 text-xs font-medium text-ink/70 dark:text-ink-dark/70">
                          <Star size={12} className="fill-amber-400 text-amber-400" /> {r.rating}
                        </span>
                      )}
                      <span
                        className={`rounded-full px-2 py-0.5 text-[11px] font-medium capitalize ${
                          r.sentiment_label === "positive"
                            ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                            : r.sentiment_label === "negative"
                              ? "bg-red-500/10 text-red-600 dark:text-red-400"
                              : "bg-slate-500/10 text-slate-600 dark:text-slate-300"
                        }`}
                      >
                        {r.sentiment_label}
                      </span>
                    </div>
                  </div>
                  {r.text && <p className="mt-1.5 line-clamp-2 text-xs text-ink/70 dark:text-ink-dark/70">{r.text}</p>}
                </div>
              ))}
              {recentReviews.length === 0 && <p className="py-6 text-center text-sm text-ink/50 dark:text-ink-dark/50">Nothing here yet.</p>}
            </div>
          </Card>
        </>
      )}
    </div>
  );
}

// Recharts' Treemap needs an explicit cell renderer to draw fill/stroke/text
// itself (unlike Bar/Pie's <Cell> children) — kept minimal: the rect, plus a
// label only when the cell is large enough to hold it without overflowing
// (see the dataviz skill's "never a clipped label" rule).
function TreemapCell({ x, y, width, height, name, size, fill }) {
  const showLabel = width > 60 && height > 28;
  return (
    <g>
      {/* Recharts' Treemap can hand the content renderer a node with no
          `fill` of its own (e.g. an implicit root/leftover node when there
          are very few leaves) — style="fill: undefined" would resolve to
          the SVG default (solid black), so fall back to the ramp's own
          lightest step rather than let that show through. */}
      <rect x={x} y={y} width={width} height={height} style={{ fill: fill ?? PINK_RAMP[0], stroke: "#fff", strokeWidth: 2 }} />
      {showLabel && (
        <text x={x + 6} y={y + 16} fontSize={11} fill="#fff" fontWeight={600}>
          {name}
        </text>
      )}
      {showLabel && (
        <text x={x + 6} y={y + 30} fontSize={10} fill="#fff" opacity={0.85}>
          {size}
        </text>
      )}
    </g>
  );
}
