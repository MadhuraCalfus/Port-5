import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, FileDown, Lightbulb, Loader2, RefreshCw, ThumbsUp } from "lucide-react";
import { api } from "../../../api";
import { Card } from "../../../components/primitives";
import { generateNykaaReportPdf } from "../../../pmReportExport";
import { MONTHS, isoWeekKey, weeksInMonth, yearOptions } from "../../../periodNav";

const REPORT_TYPES = [
  { id: "weekly", label: "Weekly" },
  { id: "monthly", label: "Monthly" },
  { id: "yearly", label: "Yearly" },
];

function StatRow({ label, value, tone }) {
  const toneClass =
    tone === "bad"
      ? "text-red-600 dark:text-red-400"
      : tone === "good"
        ? "text-emerald-600 dark:text-emerald-400"
        : "text-ink dark:text-ink-dark";
  return (
    <li className="flex items-center justify-between rounded-lg bg-black/[0.02] dark:bg-white/[0.03] px-3 py-2 text-sm">
      <span className="text-ink/70 dark:text-ink-dark/70">{label}</span>
      <span className={`font-display font-bold ${toneClass}`}>{value}</span>
    </li>
  );
}

// Same list-of-bullets shape as models.NarrativeReport, rendered as a
// dot-bullet list rather than a paragraph — mirrors ReportsActionsPage.jsx.
function BulletList({ points, dotClassName }) {
  return (
    <ul className="space-y-1">
      {(points ?? []).map((line, i) => (
        <li key={i} className="flex gap-2">
          <span className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${dotClassName}`} />
          {line}
        </li>
      ))}
    </ul>
  );
}

// Nykaa Pulse's weekly-report endpoint is brand-scoped (same underlying
// engine as brand-breakdown/narrative_ai.generate_report — see
// nykaa_insights.generate_brand_report) and, unlike the Mission side's
// /pm/insights/report, computes fresh on every GET rather than being a
// persisted upsert — no "generate" click, no 404-if-missing state, no
// separate recommended-actions list. So this mirrors
// ReportsActionsPage.jsx's narrative-card layout/styling, minus the
// generate/persist machinery that doesn't apply here. Because the engine is
// generic, its prose may say "category" when it means brand — that's
// expected, not a bug, per the Phase 3 brief.
export function NykaaPulseWeeklyReportPage() {
  const [reportType, setReportType] = useState("weekly");
  const [selectedYear, setSelectedYear] = useState(() => new Date().getFullYear());
  const [selectedMonth, setSelectedMonth] = useState(() => new Date().getMonth() + 1);
  const [selectedWeekKey, setSelectedWeekKey] = useState(() => isoWeekKey(new Date()));

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState(null);

  const weekOptions = useMemo(() => weeksInMonth(selectedYear, selectedMonth), [selectedYear, selectedMonth]);
  const yearOptionsList = useMemo(() => yearOptions(), []);

  useEffect(() => {
    if (weekOptions.length > 0 && !weekOptions.some((w) => w.key === selectedWeekKey)) {
      setSelectedWeekKey(weekOptions[0].key);
    }
  }, [weekOptions, selectedWeekKey]);

  const periodKey =
    reportType === "yearly"
      ? String(selectedYear)
      : reportType === "monthly"
        ? `${selectedYear}-${String(selectedMonth).padStart(2, "0")}`
        : selectedWeekKey;
  const periodLabel =
    reportType === "yearly"
      ? String(selectedYear)
      : reportType === "monthly"
        ? `${MONTHS[selectedMonth - 1]} ${selectedYear}`
        : (weekOptions.find((w) => w.key === selectedWeekKey)?.label ?? selectedWeekKey);

  async function load(pt, pk) {
    setLoading(true);
    setError(null);
    try {
      const r = await api.nykaaPmWeeklyReport(pt, pk);
      setData(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load(reportType, periodKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reportType, periodKey]);

  async function exportPdf() {
    if (!data) return;
    setExporting(true);
    setError(null);
    try {
      generateNykaaReportPdf({ periodType: reportType, periodLabel, report: data.report, trend: data.trend });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setExporting(false);
    }
  }

  const trend = data?.trend;
  const reportTypeLabel = reportType === "yearly" ? "Yearly" : reportType === "monthly" ? "Monthly" : "Weekly";

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-display text-lg font-semibold">{reportTypeLabel} report</h2>
        <div className="flex flex-wrap items-center gap-2">
          <div className="grid grid-cols-3 gap-1 rounded-xl bg-black/[0.04] dark:bg-white/[0.06] p-1">
            {REPORT_TYPES.map(({ id, label }) => (
              <button
                key={id}
                type="button"
                onClick={() => setReportType(id)}
                className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                  reportType === id
                    ? "bg-surface dark:bg-surface-dark text-brand dark:text-brand-dim shadow-sm"
                    : "text-ink/50 dark:text-ink-dark/50 hover:text-ink dark:hover:text-ink-dark"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

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

          {(reportType === "weekly" || reportType === "monthly") && (
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

          {reportType === "weekly" && (
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

          <button
            onClick={() => load(reportType, periodKey)}
            className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs text-ink/50 dark:text-ink-dark/50 hover:bg-black/5 dark:hover:bg-white/10"
          >
            <RefreshCw size={13} className={loading ? "animate-spin" : ""} /> Refresh
          </button>
          <button
            onClick={exportPdf}
            disabled={exporting || !data}
            className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs text-ink/50 dark:text-ink-dark/50 hover:bg-black/5 dark:hover:bg-white/10 disabled:opacity-40"
          >
            {exporting ? <Loader2 size={13} className="animate-spin" /> : <FileDown size={13} />}
            Export PDF
          </button>
        </div>
      </div>

      {error && <p className="rounded-lg bg-red-500/10 px-3 py-2 text-xs text-red-600 dark:text-red-400">{error}</p>}

      {!data ? (
        <Card className="p-8 text-center text-sm text-ink/50 dark:text-ink-dark/50">
          <span className="inline-flex items-center gap-2">
            <Loader2 size={16} className="animate-spin" /> Loading...
          </span>
        </Card>
      ) : (
        <>
          {trend && (
            <Card className="p-5">
              <h3 className="mb-3 text-sm font-semibold">This period at a glance — {periodLabel}</h3>
              <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                <StatRow label="Total reviews" value={trend.current.total_items} />
                <StatRow label="Positive" value={trend.current.sentiment_distribution.positive ?? 0} tone="good" />
                <StatRow label="Negative" value={trend.current.sentiment_distribution.negative ?? 0} tone="bad" />
                <StatRow label="Neutral" value={trend.current.sentiment_distribution.neutral ?? 0} />
                <StatRow label="Needs follow-up" value={trend.current.actionable_count} />
                <StatRow label="Average urgency" value={`${Math.round(trend.current.avg_urgency_score * 100)}%`} />
                {trend.current.rated_count > 0 && (
                  <StatRow label="Average rating" value={`★ ${trend.current.avg_rating.toFixed(1)} (${trend.current.rated_count})`} />
                )}
              </ul>
            </Card>
          )}

          <Card className="p-6">
            <h3 className="text-sm font-semibold">
              {reportTypeLabel} brand insight report — {periodLabel}
            </h3>

            <div className="mt-4 space-y-4">
              <div className="text-sm leading-relaxed text-ink/80 dark:text-ink-dark/80">
                <BulletList points={data.report.narrative} dotClassName="bg-brand/60" />
              </div>

              <div className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-xl bg-emerald-500/10 p-3.5">
                  <p className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-emerald-600 dark:text-emerald-400">
                    <ThumbsUp size={13} /> What went well
                  </p>
                  <div className="mt-1 text-sm text-ink dark:text-ink-dark">
                    <BulletList points={data.report.whats_going_well} dotClassName="bg-emerald-500/70" />
                  </div>
                </div>

                <div className="rounded-xl bg-red-500/10 p-3.5">
                  <p className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-red-600 dark:text-red-400">
                    <AlertTriangle size={13} /> Top pain point
                  </p>
                  <div className="mt-1 text-sm text-ink dark:text-ink-dark">
                    <BulletList points={data.report.top_pain_point} dotClassName="bg-red-500/70" />
                  </div>
                </div>

                <div className="rounded-xl bg-brand/10 p-3.5">
                  <p className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-brand dark:text-brand-dim">
                    <Lightbulb size={13} /> Recommendation
                  </p>
                  <div className="mt-1 text-sm text-ink dark:text-ink-dark">
                    <BulletList points={data.report.recommendation} dotClassName="bg-brand/60" />
                  </div>
                </div>
              </div>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
