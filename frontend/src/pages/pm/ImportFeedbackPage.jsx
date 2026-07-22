import { useEffect, useState } from "react";
import { Loader2, RefreshCw, Upload } from "lucide-react";
import { api } from "../../api";
import { Button, Card } from "../../components/primitives";

const SOURCE_TYPES = [
  { id: "review", label: "Reviews" },
  { id: "survey", label: "Surveys" },
];

const SENTIMENT_STYLES = {
  positive: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  neutral: "bg-slate-500/10 text-slate-600 dark:text-slate-300",
  negative: "bg-red-500/10 text-red-600 dark:text-red-400",
  mixed: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
};

export function ImportFeedbackPage() {
  const [sourceType, setSourceType] = useState("review");
  const [text, setText] = useState("");
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [items, setItems] = useState([]);
  const [loadingItems, setLoadingItems] = useState(false);

  async function loadRecent() {
    setLoadingItems(true);
    try {
      const r = await api.pmFeedback(50);
      setItems(r.items);
    } finally {
      setLoadingItems(false);
    }
  }

  useEffect(() => {
    loadRecent();
  }, []);

  async function submit() {
    const lines = text.split("\n").map((l) => l.trim()).filter(Boolean);
    if (lines.length === 0) return;
    setImporting(true);
    setError(null);
    setResult(null);
    try {
      const r = await api.pmImportFeedback(sourceType, lines);
      setResult(r);
      setText("");
      await loadRecent();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setImporting(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_1.2fr]">
      <Card className="p-6">
        <h2 className="font-display text-lg font-semibold">Import reviews or surveys</h2>
        <p className="mt-1.5 text-sm leading-relaxed text-ink/60 dark:text-ink-dark/60">
          Paste one review or survey response per line. Each is run through the same sentiment/theme/urgency
          analysis as tickets, and added to the customer voice log below.
        </p>

        <div className="mt-4 grid grid-cols-2 gap-1 rounded-xl bg-black/[0.04] dark:bg-white/[0.06] p-1">
          {SOURCE_TYPES.map(({ id, label }) => (
            <button
              key={id}
              type="button"
              onClick={() => setSourceType(id)}
              className={`rounded-lg py-2 text-xs font-medium transition ${
                sourceType === id
                  ? "bg-surface dark:bg-surface-dark text-brand dark:text-brand-dim shadow-sm"
                  : "text-ink/50 dark:text-ink-dark/50 hover:text-ink dark:hover:text-ink-dark"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={"One item per line, e.g.\nThe checkout page took forever to load today.\nLove the new dark mode!"}
          rows={10}
          className="mt-4 w-full resize-none rounded-xl border border-black/10 dark:border-white/15 bg-black/[0.02] dark:bg-white/[0.03] p-3.5 text-sm outline-none focus:border-brand/60 focus:ring-2 focus:ring-brand/20"
        />

        <div className="mt-4 flex items-center gap-3 border-t border-black/5 dark:border-white/10 pt-4">
          <Button onClick={submit} disabled={importing || !text.trim()}>
            {importing ? <Loader2 size={16} className="animate-spin" /> : <Upload size={16} />}
            {importing ? "Analyzing..." : "Import & analyze"}
          </Button>
        </div>

        {result && (
          <p className="mt-3 rounded-lg bg-emerald-500/10 px-3 py-2 text-xs text-emerald-600 dark:text-emerald-400">
            Imported {result.imported} item{result.imported === 1 ? "" : "s"}
            {result.skipped > 0 ? ` (${result.skipped} blank line${result.skipped === 1 ? "" : "s"} skipped)` : ""}.
          </p>
        )}
        {error && <p className="mt-3 rounded-lg bg-red-500/10 px-3 py-2 text-xs text-red-600 dark:text-red-400">{error}</p>}
      </Card>

      <Card className="p-6">
        <div className="flex items-center justify-between">
          <h2 className="font-display text-lg font-semibold">Customer voice log ({items.length})</h2>
          <button
            onClick={loadRecent}
            className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs text-ink/50 dark:text-ink-dark/50 hover:bg-black/5 dark:hover:bg-white/10"
          >
            <RefreshCw size={13} className={loadingItems ? "animate-spin" : ""} /> Refresh
          </button>
        </div>
        <p className="mt-1 text-sm text-ink/60 dark:text-ink-dark/60">
          Every ticket, review, and survey response analyzed so far, most recent first.
        </p>

        {items.length === 0 ? (
          <p className="mt-6 text-center text-sm text-ink/50 dark:text-ink-dark/50">
            Nothing yet — imported reviews/surveys and submitted tickets will show up here.
          </p>
        ) : (
          <div className="thin-scroll mt-4 max-h-[560px] space-y-2.5 overflow-y-auto pr-1">
            {items.map((i) => (
              <div key={i.id} className="fade-up rounded-xl border border-black/8 dark:border-white/10 p-3.5">
                <div className="flex items-start justify-between gap-3">
                  <p className="text-sm text-ink/80 dark:text-ink-dark/80">"{i.text}"</p>
                  <span className="shrink-0 rounded-full bg-black/5 dark:bg-white/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-ink/50 dark:text-ink-dark/50">
                    {i.source_type}
                  </span>
                </div>
                <div className="mt-2.5 flex flex-wrap items-center gap-2">
                  <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium capitalize ${SENTIMENT_STYLES[i.sentiment_label] ?? SENTIMENT_STYLES.neutral}`}>
                    {i.sentiment_label} ({i.sentiment_score >= 0 ? "+" : ""}{i.sentiment_score.toFixed(1)})
                  </span>
                  <span className="rounded-full bg-brand/10 px-2 py-0.5 text-[11px] font-medium text-brand dark:text-brand-dim">
                    {i.theme}
                  </span>
                  <span className="text-[11px] text-ink/50 dark:text-ink-dark/50">
                    urgency {Math.round(i.urgency_score * 100)}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
