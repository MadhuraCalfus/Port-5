import { useEffect, useMemo, useState } from "react";
import { Loader2, Search } from "lucide-react";
import { api } from "../../../api";
import { Card } from "../../../components/primitives";
import { NykaaPeriodDateControls, NykaaPeriodTypeToggle, useNykaaPeriodFilter } from "../../../components/NykaaPeriodToggle";

// The PM's raw, fully-detailed feedback list for Nykaa Pulse — the
// Overview/Analytics/Weekly Report tabs are all aggregates; this is the one
// place a PM can read individual reviews with every field (product, brand,
// category, theme, rating, sentiment, urgency), search/filter them, and
// narrow to a period. Mirrors the Mission side's ImportFeedbackPage.jsx, but
// fetches everything in one call (there's no per-period Nykaa endpoint) and
// buckets by period client-side instead.
const SENTIMENT_TABS = [
  { id: "all", label: "All sentiment" },
  { id: "positive", label: "Positive" },
  { id: "neutral", label: "Neutral" },
  { id: "negative", label: "Negative" },
];

const SENTIMENT_STYLES = {
  positive: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  neutral: "bg-slate-500/10 text-slate-600 dark:text-slate-300",
  negative: "bg-red-500/10 text-red-600 dark:text-red-400",
};

// Same plain-threshold 3-way bucket as the Mission side's ImportFeedbackPage.
function urgencyTier(score) {
  if (score >= 0.6) return "High";
  if (score >= 0.3) return "Medium";
  return "Low";
}

const URGENCY_STYLES = {
  High: "bg-red-500/10 text-red-600 dark:text-red-400",
  Medium: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
  Low: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
};

export function NykaaAllFeedbackPage() {
  const [items, setItems] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [sentimentTab, setSentimentTab] = useState("all");
  const picker = useNykaaPeriodFilter("all");

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

  const categoryOptions = useMemo(() => {
    if (!items) return [];
    return [...new Set(items.map((i) => i.category).filter(Boolean))].sort();
  }, [items]);

  const filtered = useMemo(() => {
    if (!items) return [];
    let rows = items;
    if (picker.range) {
      const [start, end] = picker.range;
      rows = rows.filter((i) => {
        const created = new Date(i.created_at);
        return created >= start && created < end;
      });
    }
    const q = search.trim().toLowerCase();
    return rows
      .filter((i) => categoryFilter === "all" || i.category === categoryFilter)
      .filter((i) => sentimentTab === "all" || i.sentiment_label === sentimentTab)
      .filter(
        (i) =>
          !q ||
          i.text.toLowerCase().includes(q) ||
          i.category?.toLowerCase().includes(q) ||
          i.theme?.toLowerCase().includes(q) ||
          i.brand?.toLowerCase().includes(q) ||
          i.product_name?.toLowerCase().includes(q),
      )
      .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  }, [items, picker.range, categoryFilter, sentimentTab, search]);

  return (
    <div className="space-y-6">
      <h2 className="font-display text-lg font-semibold">
        All feedback ({filtered.length}
        {items && items.length !== filtered.length ? ` of ${items.length}` : ""})
      </h2>

      <Card className="p-5">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-1.5 rounded-lg border border-black/10 dark:border-white/15 px-2 py-1 text-xs text-ink/50 dark:text-ink-dark/50">
              <Search size={13} />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search text, brand, product, category..."
                className="w-48 bg-transparent text-xs text-ink dark:text-ink-dark placeholder:text-ink/40 dark:placeholder:text-ink-dark/40 outline-none"
              />
            </label>
            <button
              onClick={load}
              className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs text-ink/50 dark:text-ink-dark/50 hover:bg-black/5 dark:hover:bg-white/10"
            >
              {loading ? <Loader2 size={13} className="animate-spin" /> : null} Refresh
            </button>
          </div>
          <div className="ml-auto flex flex-wrap items-center gap-2">
            <NykaaPeriodDateControls picker={picker} />

            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="rounded-lg border border-black/10 dark:border-white/15 bg-transparent px-2 py-1.5 text-xs text-ink dark:text-ink-dark"
            >
              <option value="all">All categories</option>
              {categoryOptions.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>

            <select
              value={sentimentTab}
              onChange={(e) => setSentimentTab(e.target.value)}
              className="rounded-lg border border-black/10 dark:border-white/15 bg-transparent px-2 py-1.5 text-xs text-ink dark:text-ink-dark"
            >
              {SENTIMENT_TABS.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.label}
                </option>
              ))}
            </select>

            <NykaaPeriodTypeToggle picker={picker} className="ml-auto" />
          </div>
        </div>

        {error && <p className="mt-3 rounded-lg bg-red-500/10 px-3 py-2 text-xs text-red-600 dark:text-red-400">{error}</p>}

        <div className="thin-scroll mt-3 max-h-[650px] overflow-auto rounded-xl border border-black/10 dark:border-white/15">
          <table className="w-full text-left text-sm">
            <thead className="sticky top-0 bg-black/[0.03] dark:bg-white/[0.05] text-[11px] uppercase tracking-wide text-ink/40 dark:text-ink-dark/40">
              <tr>
                <th className="px-3 py-2">Date</th>
                <th className="px-3 py-2">Product</th>
                <th className="px-3 py-2">Details</th>
                <th className="px-3 py-2">Category</th>
                <th className="px-3 py-2">Theme</th>
                <th className="px-3 py-2">Rating</th>
                <th className="px-3 py-2">Sentiment</th>
                <th className="px-3 py-2">Confidence</th>
                <th className="px-3 py-2">Urgency</th>
                <th className="px-3 py-2">Actionable</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-black/5 dark:divide-white/10">
              {!items ? (
                <tr>
                  <td colSpan={10} className="px-3 py-6 text-center text-sm text-ink/50 dark:text-ink-dark/50">
                    <span className="inline-flex items-center gap-2">
                      <Loader2 size={14} className="animate-spin" /> Loading...
                    </span>
                  </td>
                </tr>
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={10} className="px-3 py-6 text-center text-sm text-ink/50 dark:text-ink-dark/50">
                    {search ? `Nothing matches "${search}".` : "Nothing here yet."}
                  </td>
                </tr>
              ) : (
                filtered.map((i) => {
                  const tier = urgencyTier(i.urgency_score);
                  return (
                    <tr key={i.source_ref} className="align-top">
                      <td className="whitespace-nowrap px-3 py-2.5 text-[11px] text-ink/50 dark:text-ink-dark/50">
                        {new Date(i.created_at).toLocaleDateString()}
                      </td>
                      <td className="w-36 px-3 py-2.5 text-ink/80 dark:text-ink-dark/80">
                        <div className="break-words font-medium">{i.product_name}</div>
                        <div className="text-[11px] text-ink/40 dark:text-ink-dark/40">{i.brand}</div>
                      </td>
                      <td className="w-72 px-3 py-2.5 text-ink/80 dark:text-ink-dark/80">
                        <div className="break-words">{i.text}</div>
                      </td>
                      <td className="px-3 py-2.5">
                        <span className="rounded-full bg-brand/10 px-2 py-0.5 text-[11px] font-medium text-brand dark:text-brand-dim">
                          {i.category}
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-3 py-2.5 text-xs text-ink/70 dark:text-ink-dark/70">
                        {i.theme ?? <span className="text-ink/30 dark:text-ink-dark/30">—</span>}
                      </td>
                      <td className="px-3 py-2.5 text-xs text-ink/70 dark:text-ink-dark/70">
                        {i.rating ? `★ ${i.rating}` : <span className="text-ink/30 dark:text-ink-dark/30">—</span>}
                      </td>
                      <td className="px-3 py-2.5">
                        <span
                          className={`rounded-full px-2 py-0.5 text-[11px] font-medium capitalize ${SENTIMENT_STYLES[i.sentiment_label] ?? SENTIMENT_STYLES.neutral}`}
                        >
                          {i.sentiment_label}
                        </span>
                      </td>
                      <td className="px-3 py-2.5 text-ink/70 dark:text-ink-dark/70">{Math.round(Math.abs(i.sentiment_score) * 100)}%</td>
                      <td className="px-3 py-2.5">
                        <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${URGENCY_STYLES[tier]}`}>{tier}</span>
                      </td>
                      <td className="px-3 py-2.5">{i.is_actionable_ticket ? "Yes" : "No"}</td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
