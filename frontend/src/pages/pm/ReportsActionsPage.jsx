import { useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, FileDown, Lightbulb, ListChecks, Loader2, Sparkles, ThumbsUp } from "lucide-react";
import { api } from "../../api";
import { Button, Card } from "../../components/primitives";
import { generatePmReportPdf } from "../../pmReportExport";
import { MONTHS, isoWeekKey, weeksInMonth, yearOptions } from "../../periodNav";

const REPORT_TYPES = [
  { id: "weekly", label: "Weekly" },
  { id: "monthly", label: "Monthly" },
  { id: "yearly", label: "Yearly" },
];

const MAX_VISIBLE_ACTIONS = 5;

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

// Every narrative field is a list of short bullet points (models.NarrativeReport)
// rather than a paragraph — rendered as a dot-bullet list, same visual
// language as "Suggested actions" below.
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

export function ReportsActionsPage() {
  const [reportType, setReportType] = useState("weekly");
  const [selectedYear, setSelectedYear] = useState(() => new Date().getFullYear());
  const [selectedMonth, setSelectedMonth] = useState(() => new Date().getMonth() + 1);
  const [selectedWeekKey, setSelectedWeekKey] = useState(() => isoWeekKey(new Date()));

  const [report, setReport] = useState(null);
  const [reportMissing, setReportMissing] = useState(false);
  const [actions, setActions] = useState([]);
  const [trend, setTrend] = useState(null);
  const [generatingReport, setGeneratingReport] = useState(false);
  const [generatingActions, setGeneratingActions] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  // Tracks which (type, period_key) combos have already had an auto-generate
  // attempt this mount — a ref (not state) so the flag is set synchronously,
  // before any await yields control. Needed because React StrictMode's
  // dev-mode double effect-invoke would otherwise race two concurrent
  // loadAll() calls into each seeing "nothing generated yet" and both
  // generating, producing duplicate actions (generate is intentionally
  // non-idempotent — see its docstring — so this has to be prevented on the
  // caller's side).
  const autoGenAttempted = useRef({});
  // Guards every state update below against a slower, superseded load (e.g.
  // switching Yearly 2026 -> 2025 while 2026's report/actions are still
  // generating) resolving late and clobbering the current period's state
  // with stale data.
  const loadId = useRef(0);

  const weekOptions = useMemo(() => weeksInMonth(selectedYear, selectedMonth), [selectedYear, selectedMonth]);
  const yearOptionsList = useMemo(() => yearOptions(), []);

  // Keep the selected week valid whenever the year/month narrows its options.
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

  async function loadReport(pt, pk, id) {
    try {
      const r = await api.pmGetReport(pt, pk);
      if (id === loadId.current) {
        setReport(r);
        setReportMissing(false);
      }
      return r;
    } catch (e) {
      if (e instanceof Error && e.message.startsWith("404")) {
        if (id === loadId.current) {
          setReport(null);
          setReportMissing(true);
        }
        return null;
      }
      throw e;
    }
  }

  async function loadActions(pt, pk, id) {
    const r = await api.pmListActions(pt, pk);
    // "Generate actions" only ever appends (so re-running it after new
    // feedback never erases something a PM already read) — over repeated
    // generations that means far more sit in the database than anyone
    // should have to read in one sitting. Newest-first + capped keeps this
    // a quick skim instead of a growing wall of text.
    const recent = [...r.actions].sort((a, b) => new Date(b.created_at) - new Date(a.created_at)).slice(0, MAX_VISIBLE_ACTIONS);
    if (id === loadId.current) setActions(recent);
    return recent;
  }

  async function loadAll(pt, pk) {
    const id = ++loadId.current;
    setLoading(true);
    const genKey = `${pt}:${pk}`;
    const alreadyAttempted = autoGenAttempted.current[genKey];
    autoGenAttempted.current[genKey] = true;
    try {
      const [existingReport, existingActions, periodTrend] = await Promise.all([
        loadReport(pt, pk, id),
        loadActions(pt, pk, id),
        api.pmTrend(pt, pk),
      ]);
      if (id === loadId.current) {
        setTrend(periodTrend);
      }
      // Nobody should have to know to click "Generate" — a period with no
      // report/actions yet gets them generated automatically on first visit.
      if (!alreadyAttempted) {
        const toGenerate = [];
        if (!existingReport) toGenerate.push(generateReport(pt, pk, id));
        if (existingActions.length === 0) toGenerate.push(generateActions(pt, pk, id));
        if (toGenerate.length > 0) await Promise.all(toGenerate);
      }
    } finally {
      if (id === loadId.current) setLoading(false);
    }
  }

  useEffect(() => {
    loadAll(reportType, periodKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reportType, periodKey]);

  async function generateReport(pt = reportType, pk = periodKey, id = loadId.current) {
    setGeneratingReport(true);
    try {
      const r = await api.pmGenerateReport(pt, pk);
      if (id === loadId.current) {
        setReport(r);
        setReportMissing(false);
      }
    } finally {
      if (id === loadId.current) setGeneratingReport(false);
    }
  }

  async function generateActions(pt = reportType, pk = periodKey, id = loadId.current) {
    setGeneratingActions(true);
    try {
      await api.pmGenerateActions(pt, pk);
      await loadActions(pt, pk, id);
    } finally {
      if (id === loadId.current) setGeneratingActions(false);
    }
  }

  async function exportPdf() {
    if (!report || !trend) return;
    setExporting(true);
    setError(null);
    try {
      const items = await api.pmPeriodItems(reportType, periodKey);
      generatePmReportPdf({ periodType: reportType, report, trend, actions, items: items.items });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-display text-lg font-semibold">Weekly, monthly &amp; yearly report</h2>
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
            onClick={exportPdf}
            disabled={exporting || !report || !trend}
            title={!report ? "Generate a report first" : undefined}
            className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs text-ink/50 dark:text-ink-dark/50 hover:bg-black/5 dark:hover:bg-white/10 disabled:opacity-40"
          >
            {exporting ? <Loader2 size={13} className="animate-spin" /> : <FileDown size={13} />}
            Export PDF
          </button>
        </div>
      </div>

      {error && <p className="rounded-lg bg-red-500/10 px-3 py-2 text-xs text-red-600 dark:text-red-400">{error}</p>}

      {loading ? (
        <Card className="p-8 text-center text-sm text-ink/50 dark:text-ink-dark/50">Loading...</Card>
      ) : (
        <>
          {trend && (
            <Card className="p-5">
              <h3 className="mb-3 text-sm font-semibold">This period at a glance — {periodLabel}</h3>
              <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                <StatRow label="Total feedback" value={trend.current.total_items} />
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
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold">
                {reportType === "yearly" ? "Yearly" : reportType === "monthly" ? "Monthly" : "Weekly"} insight report — {periodLabel}
              </h3>
              <Button onClick={() => generateReport()} disabled={generatingReport} variant={report ? "ghost" : "primary"}>
                {generatingReport ? <Loader2 size={15} className="animate-spin" /> : <Sparkles size={15} />}
                {generatingReport ? "Generating..." : report ? "Regenerate" : "Generate report"}
              </Button>
            </div>

            {!report && reportMissing && (
              <p className="mt-6 text-center text-sm text-ink/50 dark:text-ink-dark/50">
                No report generated for this period yet — click "Generate report" above.
              </p>
            )}

            {report && (
              <div className="mt-4 space-y-4">
                <p className="text-xs text-ink/50 dark:text-ink-dark/50">
                  {report.period_start} – {report.period_end}
                </p>

                <div className="text-sm leading-relaxed text-ink/80 dark:text-ink-dark/80">
                  <BulletList points={report.narrative.narrative} dotClassName="bg-brand/60" />
                </div>

                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="rounded-xl bg-emerald-500/10 p-3.5">
                    <p className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-emerald-600 dark:text-emerald-400">
                      <ThumbsUp size={13} /> What went well
                    </p>
                    <div className="mt-1 text-sm text-ink dark:text-ink-dark">
                      <BulletList points={report.narrative.whats_going_well} dotClassName="bg-emerald-500/70" />
                    </div>
                  </div>

                  <div className="rounded-xl bg-red-500/10 p-3.5">
                    <p className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-red-600 dark:text-red-400">
                      <AlertTriangle size={13} /> Top pain point
                    </p>
                    <div className="mt-1 text-sm text-ink dark:text-ink-dark">
                      <BulletList points={report.narrative.top_pain_point} dotClassName="bg-red-500/70" />
                    </div>
                  </div>

                  <div className="rounded-xl bg-brand/10 p-3.5">
                    <p className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-brand dark:text-brand-dim">
                      <Lightbulb size={13} /> Recommendation
                    </p>
                    <div className="mt-1 text-sm text-ink dark:text-ink-dark">
                      <BulletList points={report.narrative.recommendation} dotClassName="bg-brand/60" />
                    </div>
                  </div>
                </div>

                <div className="border-t border-black/5 dark:border-white/10 pt-4">
                  <div className="flex items-center justify-between">
                    <h4 className="text-sm font-semibold">Suggested actions</h4>
                    <button
                      onClick={() => generateActions()}
                      disabled={generatingActions}
                      className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs text-ink/50 dark:text-ink-dark/50 hover:bg-black/5 dark:hover:bg-white/10 disabled:opacity-40"
                    >
                      {generatingActions ? <Loader2 size={13} className="animate-spin" /> : <ListChecks size={13} />}
                      {generatingActions ? "Generating..." : "Generate actions"}
                    </button>
                  </div>

                  {actions.length === 0 && !generatingActions ? (
                    <p className="mt-4 text-center text-sm text-ink/50 dark:text-ink-dark/50">
                      No specific concerns stood out this period — click "Generate actions" to check again.
                    </p>
                  ) : (
                    <ul className="thin-scroll mt-3 max-h-[400px] space-y-1.5 overflow-y-auto pr-1">
                      {actions.map((a) => (
                        <li key={a.id} className="flex gap-2 text-sm text-ink/80 dark:text-ink-dark/80">
                          <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand/60" />
                          {a.action_text}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
