import { useEffect, useState } from "react";
import { Loader2, Plus, RefreshCw, Send, Trash2 } from "lucide-react";
import { api } from "../../api";
import { Button, Card } from "../../components/primitives";

// Mirrors backend/app/models.py's SURVEY_SCALE_LABELS — every survey uses
// this exact 5-point scale, not a PM choice (see main.py's
// _survey_response_type for why: fixed negative/neutral/positive zones).
const SURVEY_SCALE_LABELS = ["Worst", "Bad", "Okay", "Good", "Best"];

const STATUS_STYLES = {
  draft: "bg-slate-500/10 text-slate-600 dark:text-slate-300",
  sent: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
};

export function CreateSurveyPage() {
  const [surveys, setSurveys] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const [title, setTitle] = useState("");
  const [questions, setQuestions] = useState([""]);
  const [creating, setCreating] = useState(false);
  const [sendingId, setSendingId] = useState(null);

  async function load() {
    setLoading(true);
    try {
      const r = await api.pmListSurveys();
      setSurveys(r.surveys);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  function updateQuestion(i, value) {
    setQuestions((prev) => prev.map((q, idx) => (idx === i ? value : q)));
  }

  function addQuestion() {
    setQuestions((prev) => [...prev, ""]);
  }

  function removeQuestion(i) {
    setQuestions((prev) => (prev.length > 1 ? prev.filter((_, idx) => idx !== i) : prev));
  }

  async function submit(e) {
    e.preventDefault();
    const cleaned = questions.map((q) => q.trim()).filter(Boolean);
    if (!title.trim() || cleaned.length === 0) return;
    setCreating(true);
    setError(null);
    try {
      await api.pmCreateSurvey(title.trim(), cleaned);
      setTitle("");
      setQuestions([""]);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setCreating(false);
    }
  }

  async function send(survey) {
    if (!window.confirm(`Send "${survey.title}" to every customer now? This can't be undone.`)) return;
    setSendingId(survey.id);
    try {
      const updated = await api.pmSendSurvey(survey.id);
      setSurveys((prev) => prev.map((s) => (s.id === survey.id ? { ...updated, response_count: s.response_count } : s)));
    } finally {
      setSendingId(null);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_1.3fr]">
      <Card className="p-5">
        <h2 className="font-display text-lg font-semibold">Create a survey</h2>
        <p className="mt-1 text-sm text-ink/60 dark:text-ink-dark/60">
          Write your own questions and send them to every customer when you're ready.
        </p>

        <form onSubmit={submit} className="mt-4 space-y-4">
          <label className="block text-xs text-ink/70 dark:text-ink-dark/70">
            Survey title
            <input
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. How's the new dashboard working for you?"
              className="mt-1 w-full rounded-lg border border-black/10 dark:border-white/15 bg-transparent px-3 py-2 text-sm text-ink dark:text-ink-dark outline-none focus:border-brand/60"
            />
          </label>

          <div className="rounded-lg bg-black/[0.02] dark:bg-white/[0.03] px-3 py-2 text-xs text-ink/60 dark:text-ink-dark/60">
            Every question uses the same scale: <strong className="text-ink dark:text-ink-dark">{SURVEY_SCALE_LABELS.join(" → ")}</strong>
          </div>

          <div>
            <p className="text-xs text-ink/70 dark:text-ink-dark/70">Questions</p>
            <div className="mt-1.5 space-y-2">
              {questions.map((q, i) => (
                <div key={i} className="flex items-center gap-1.5">
                  <input
                    value={q}
                    onChange={(e) => updateQuestion(i, e.target.value)}
                    placeholder={`Question ${i + 1}`}
                    className="w-full rounded-lg border border-black/10 dark:border-white/15 bg-transparent px-3 py-2 text-sm text-ink dark:text-ink-dark outline-none focus:border-brand/60"
                  />
                  {questions.length > 1 && (
                    <button
                      type="button"
                      onClick={() => removeQuestion(i)}
                      className="grid h-8 w-8 shrink-0 place-items-center rounded-lg text-ink/40 dark:text-ink-dark/40 hover:bg-red-500/10 hover:text-red-500"
                      aria-label="Remove question"
                    >
                      <Trash2 size={14} />
                    </button>
                  )}
                </div>
              ))}
            </div>
            <button
              type="button"
              onClick={addQuestion}
              className="mt-2 inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs font-medium text-brand dark:text-brand-dim hover:bg-brand/10"
            >
              <Plus size={13} /> Add question
            </button>
          </div>

          {error && <p className="rounded-lg bg-red-500/10 px-3 py-2 text-xs text-red-600 dark:text-red-400">{error}</p>}

          <Button type="submit" disabled={creating}>
            {creating ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />}
            {creating ? "Creating..." : "Create survey"}
          </Button>
        </form>
      </Card>

      <Card className="p-5">
        <div className="flex items-center justify-between">
          <h2 className="font-display text-lg font-semibold">Your surveys</h2>
          <button
            onClick={load}
            className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs text-ink/50 dark:text-ink-dark/50 hover:bg-black/5 dark:hover:bg-white/10"
          >
            <RefreshCw size={13} className={loading ? "animate-spin" : ""} /> Refresh
          </button>
        </div>
        {!surveys ? (
          <p className="py-8 text-center text-sm text-ink/50 dark:text-ink-dark/50">{loading ? "Loading..." : ""}</p>
        ) : surveys.length === 0 ? (
          <p className="py-8 text-center text-sm text-ink/50 dark:text-ink-dark/50">
            No surveys yet — create one on the left to get started.
          </p>
        ) : (
          <div className="thin-scroll mt-3 max-h-[560px] overflow-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-[11px] uppercase tracking-wide text-ink/40 dark:text-ink-dark/40">
                <tr>
                  <th className="px-2 py-2">Title</th>
                  <th className="px-2 py-2">Scale</th>
                  <th className="px-2 py-2">Questions</th>
                  <th className="px-2 py-2">Created</th>
                  <th className="px-2 py-2">Status</th>
                  <th className="px-2 py-2">Responses</th>
                  <th className="px-2 py-2"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-black/5 dark:divide-white/10">
                {surveys.map((s) => (
                  <tr key={s.id} className="align-top">
                    <td className="max-w-[180px] px-2 py-2.5 font-medium text-ink dark:text-ink-dark">{s.title}</td>
                    <td className="px-2 py-2.5 text-ink/70 dark:text-ink-dark/70">{s.scale_points}-point</td>
                    <td className="px-2 py-2.5 text-ink/70 dark:text-ink-dark/70">{s.questions.length}</td>
                    <td className="whitespace-nowrap px-2 py-2.5 text-[11px] text-ink/50 dark:text-ink-dark/50">
                      {new Date(s.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-2 py-2.5">
                      <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium capitalize ${STATUS_STYLES[s.status]}`}>{s.status}</span>
                    </td>
                    <td className="px-2 py-2.5 text-ink/70 dark:text-ink-dark/70">{s.response_count}</td>
                    <td className="px-2 py-2.5">
                      {s.status === "draft" && (
                        <button
                          onClick={() => send(s)}
                          disabled={sendingId === s.id}
                          className="inline-flex items-center gap-1.5 rounded-lg bg-brand/10 px-2.5 py-1.5 text-xs font-medium text-brand dark:text-brand-dim hover:bg-brand/20 disabled:opacity-40"
                        >
                          {sendingId === s.id ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />}
                          Send
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
