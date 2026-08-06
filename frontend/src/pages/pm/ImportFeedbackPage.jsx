import { useEffect, useMemo, useState } from "react";
import { Loader2, Search } from "lucide-react";
import { api } from "../../api";
import { Card } from "../../components/primitives";
import { MONTHS, dayKey, daysInMonth, isoWeekKey, weeksInMonth, yearOptions } from "../../periodNav";

const PERIOD_TYPES = [
  { id: "all", label: "All time" },
  { id: "daily", label: "Daily" },
  { id: "weekly", label: "Weekly" },
  { id: "monthly", label: "Monthly" },
  { id: "yearly", label: "Yearly" },
];

const CATEGORIES = [
  "Product Quality & Fit",
  "Packaging & Damage",
  "Delivery & Logistics",
  "Review & App Flow Friction",
  "Authenticity & Trust",
  "Personalization Mismatch",
  "Pricing & Offers",
  "Rewards & Loyalty",
  "Customer Support",
  "General Praise / Other",
];

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

// A 3-way bucket for the raw 0-1 urgency_score — plain thresholds, not an
// LLM judgment, so the same score always lands in the same tier.
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

export function ImportFeedbackPage() {
  const [items, setItems] = useState([]);
  const [loadingItems, setLoadingItems] = useState(false);

  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [sentimentTab, setSentimentTab] = useState("all");

  const [periodType, setPeriodType] = useState("all");
  const [selectedYear, setSelectedYear] = useState(() => new Date().getFullYear());
  const [selectedMonth, setSelectedMonth] = useState(() => new Date().getMonth() + 1);
  const [selectedWeekKey, setSelectedWeekKey] = useState(() => isoWeekKey(new Date()));
  const [selectedDayKey, setSelectedDayKey] = useState(() => dayKey(new Date()));

  const yearOptionsList = useMemo(() => yearOptions(), []);
  const weekOptions = useMemo(() => weeksInMonth(selectedYear, selectedMonth), [selectedYear, selectedMonth]);
  const dayOptions = useMemo(() => daysInMonth(selectedYear, selectedMonth), [selectedYear, selectedMonth]);

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

  async function load(pt, pk) {
    setLoadingItems(true);
    try {
      const r = pt === "all" ? await api.pmFeedback(500) : await api.pmPeriodItems(pt, pk);
      setItems(r.items);
    } finally {
      setLoadingItems(false);
    }
  }

  useEffect(() => {
    load(periodType, periodKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [periodType, periodKey]);

  const filtered = useMemo(() => {
    return items
      .filter((i) => categoryFilter === "all" || i.category === categoryFilter)
      .filter((i) => sentimentTab === "all" || i.sentiment_label === sentimentTab)
      .filter(
        (i) =>
          !search.trim() ||
          i.text.toLowerCase().includes(search.trim().toLowerCase()) ||
          i.category?.toLowerCase().includes(search.trim().toLowerCase()) ||
          i.theme?.toLowerCase().includes(search.trim().toLowerCase()),
      )
      .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  }, [items, categoryFilter, sentimentTab, search]);

  return (
    <div className="space-y-6">
      <h2 className="font-display text-lg font-semibold">All feedback ({items.length})</h2>

      <Card className="p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            {periodType !== "all" && (
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
            )}

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

            <div className="grid grid-cols-5 gap-1 rounded-xl bg-black/[0.04] dark:bg-white/[0.06] p-1">
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

            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="rounded-lg border border-black/10 dark:border-white/15 bg-transparent px-2 py-1.5 text-xs text-ink dark:text-ink-dark"
            >
              <option value="all">All categories</option>
              {CATEGORIES.map((c) => (
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
          </div>
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-1.5 rounded-lg border border-black/10 dark:border-white/15 px-2 py-1 text-xs text-ink/50 dark:text-ink-dark/50">
              <Search size={13} />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search text, category, or theme..."
                className="w-40 bg-transparent text-xs text-ink dark:text-ink-dark placeholder:text-ink/40 dark:placeholder:text-ink-dark/40 outline-none"
              />
            </label>
            <button
              onClick={() => load(periodType, periodKey)}
              className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs text-ink/50 dark:text-ink-dark/50 hover:bg-black/5 dark:hover:bg-white/10"
            >
              {loadingItems ? <Loader2 size={13} className="animate-spin" /> : null} Refresh
            </button>
          </div>
        </div>

        <div className="thin-scroll mt-3 max-h-[650px] overflow-auto rounded-xl border border-black/10 dark:border-white/15">
          <table className="w-full text-left text-sm">
            <thead className="sticky top-0 bg-black/[0.03] dark:bg-white/[0.05] text-[11px] uppercase tracking-wide text-ink/40 dark:text-ink-dark/40">
              <tr>
                <th className="px-3 py-2">Date</th>
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
              {filtered.map((i) => {
                const tier = urgencyTier(i.urgency_score);
                return (
                  <tr key={i.id} className="align-top">
                    <td className="whitespace-nowrap px-3 py-2.5 text-[11px] text-ink/50 dark:text-ink-dark/50">
                      {new Date(i.created_at).toLocaleDateString()}
                    </td>
                    <td className="max-w-sm px-3 py-2.5 text-ink/80 dark:text-ink-dark/80">{i.text}</td>
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
                      <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium capitalize ${SENTIMENT_STYLES[i.sentiment_label] ?? SENTIMENT_STYLES.neutral}`}>
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
              })}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={9} className="px-3 py-6 text-center text-sm text-ink/50 dark:text-ink-dark/50">
                    {search ? `Nothing matches "${search}".` : "Nothing here yet."}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
