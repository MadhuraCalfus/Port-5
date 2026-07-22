import { useEffect, useState } from "react";
import { Check, ListChecks, Loader2, Sparkles, Square } from "lucide-react";
import { api } from "../../api";
import { Button, Card, ModePill } from "../../components/primitives";

const PERIOD_TYPES = [
  { id: "daily", label: "Daily" },
  { id: "weekly", label: "Weekly" },
  { id: "monthly", label: "Monthly" },
  { id: "yearly", label: "Yearly" },
];

export function ReportsActionsPage() {
  const [periodType, setPeriodType] = useState("weekly");
  const [report, setReport] = useState(null);
  const [reportMissing, setReportMissing] = useState(false);
  const [actions, setActions] = useState([]);
  const [generatingReport, setGeneratingReport] = useState(false);
  const [generatingActions, setGeneratingActions] = useState(false);
  const [loading, setLoading] = useState(false);

  async function loadReport(pt) {
    try {
      setReport(await api.pmGetReport(pt));
      setReportMissing(false);
    } catch (e) {
      if (e instanceof Error && e.message.startsWith("404")) {
        setReport(null);
        setReportMissing(true);
      } else {
        throw e;
      }
    }
  }

  async function loadActions(pt) {
    const r = await api.pmListActions(pt);
    setActions(r.actions);
  }

  async function loadAll(pt) {
    setLoading(true);
    try {
      await Promise.all([loadReport(pt), loadActions(pt)]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll(periodType);
  }, [periodType]);

  async function generateReport() {
    setGeneratingReport(true);
    try {
      setReport(await api.pmGenerateReport(periodType));
      setReportMissing(false);
    } finally {
      setGeneratingReport(false);
    }
  }

  async function generateActions() {
    setGeneratingActions(true);
    try {
      await api.pmGenerateActions(periodType);
      await loadActions(periodType);
    } finally {
      setGeneratingActions(false);
    }
  }

  async function toggleAction(action) {
    const next = action.status === "done" ? "pending" : "done";
    setActions((prev) => prev.map((a) => (a.id === action.id ? { ...a, status: next } : a)));
    try {
      await api.pmUpdateActionStatus(action.id, next);
    } catch {
      setActions((prev) => prev.map((a) => (a.id === action.id ? { ...a, status: action.status } : a)));
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-display text-lg font-semibold">Insight reports &amp; actions</h2>
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
      </div>

      {loading ? (
        <Card className="p-8 text-center text-sm text-ink/50 dark:text-ink-dark/50">Loading...</Card>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[1.3fr_1fr]">
          <Card className="p-6">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold">{periodType[0].toUpperCase() + periodType.slice(1)} insight report</h3>
              <Button onClick={generateReport} disabled={generatingReport} variant={report ? "ghost" : "primary"}>
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
                <div className="flex items-center gap-2 text-[11px] text-ink/50 dark:text-ink-dark/50">
                  <ModePill mode={report.mode} model={report.model_used} />
                  <span>
                    {report.period_start} – {report.period_end}
                  </span>
                </div>

                <p className="font-display text-lg font-semibold text-ink dark:text-ink-dark">
                  {report.narrative.headline}
                </p>

                <ul className="space-y-1.5">
                  {report.narrative.key_findings.map((f, i) => (
                    <li key={i} className="flex gap-2.5 text-sm text-ink/80 dark:text-ink-dark/80">
                      <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand/60" />
                      {f}
                    </li>
                  ))}
                </ul>

                <p className="text-sm leading-relaxed text-ink/70 dark:text-ink-dark/70">{report.narrative.narrative}</p>

                <div className="rounded-xl bg-brand/10 p-3.5">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-brand dark:text-brand-dim">
                    Bottom line
                  </p>
                  <p className="mt-1 text-sm font-medium text-ink dark:text-ink-dark">{report.narrative.bottom_line}</p>
                </div>
              </div>
            )}
          </Card>

          <Card className="p-6">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold">Recommended actions</h3>
              <button
                onClick={generateActions}
                disabled={generatingActions}
                className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs text-ink/50 dark:text-ink-dark/50 hover:bg-black/5 dark:hover:bg-white/10"
              >
                {generatingActions ? <Loader2 size={13} className="animate-spin" /> : <ListChecks size={13} />}
                {generatingActions ? "Generating..." : "Generate actions"}
              </button>
            </div>

            {actions.length === 0 ? (
              <p className="mt-6 text-center text-sm text-ink/50 dark:text-ink-dark/50">
                No actions yet — click "Generate actions" to get AI recommendations for this period's themes.
              </p>
            ) : (
              <div className="thin-scroll mt-4 max-h-[520px] space-y-2.5 overflow-y-auto pr-1">
                {actions.map((a) => (
                  <div
                    key={a.id}
                    className={`rounded-xl border border-black/8 dark:border-white/10 p-3.5 ${a.status === "done" ? "opacity-50" : ""}`}
                  >
                    <div className="flex items-start gap-2.5">
                      <button
                        onClick={() => toggleAction(a)}
                        aria-label={a.status === "done" ? "Mark pending" : "Mark done"}
                        className="mt-0.5 shrink-0 text-ink/40 dark:text-ink-dark/40 hover:text-brand dark:hover:text-brand-dim"
                      >
                        {a.status === "done" ? <Check size={16} className="text-emerald-600 dark:text-emerald-400" /> : <Square size={16} />}
                      </button>
                      <div>
                        {a.theme && (
                          <span className="inline-flex items-center rounded-full bg-brand/10 px-2 py-0.5 text-[11px] font-medium text-brand dark:text-brand-dim">
                            {a.theme}
                          </span>
                        )}
                        <p className={`mt-1.5 text-sm font-medium text-ink dark:text-ink-dark ${a.status === "done" ? "line-through" : ""}`}>
                          {a.action_text}
                        </p>
                        {a.rationale && <p className="mt-1 text-xs text-ink/50 dark:text-ink-dark/50">{a.rationale}</p>}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
