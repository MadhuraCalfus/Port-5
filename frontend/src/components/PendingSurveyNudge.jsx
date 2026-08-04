import { useEffect, useState } from "react";
import { Loader2, PartyPopper, Send } from "lucide-react";
import { api } from "../api";
import { Button, Card, Modal } from "./primitives";

// Mirrors backend/app/models.py's SURVEY_SCALE_LABELS — every custom
// survey uses this exact 5-point scale.
const SCALE_LABELS = ["Worst", "Bad", "Okay", "Good", "Best"];

// The PM's own ad-hoc surveys, distinct from any fixed rating form a
// customer page might also show — shown as a friendly floating card rather
// than forcing it on the customer, and answered one at a time if more than
// one is pending.
function PendingSurveyCard({ survey, onAnswered }) {
  const [answers, setAnswers] = useState(() => Array(survey.questions.length).fill(null));
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const allAnswered = answers.every((a) => a !== null);

  async function submit() {
    setSubmitting(true);
    setError(null);
    try {
      await api.answerSurvey(survey.id, answers);
      onAnswered();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <div className="fade-up fixed bottom-6 left-1/2 z-40 w-[min(92vw,26rem)] -translate-x-1/2">
        <Card className="flex items-center gap-3 p-4 shadow-xl">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-brand/10 text-brand dark:text-brand-dim">
            <PartyPopper size={18} />
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium text-ink dark:text-ink-dark">Hey! We've got a quick new survey for you 🎉</p>
            <p className="truncate text-xs text-ink/50 dark:text-ink-dark/50">{survey.title}</p>
          </div>
          <Button className="shrink-0 px-3 py-2 text-xs" onClick={() => setOpen(true)}>
            Answer it
          </Button>
        </Card>
      </div>

      {open && (
        <Modal title={survey.title} onClose={() => setOpen(false)}>
          <div className="thin-scroll max-h-[60vh] space-y-5 overflow-y-auto pr-1">
            {survey.questions.map((question, qi) => (
              <div key={qi}>
                <p className="text-sm text-ink dark:text-ink-dark">
                  {qi + 1}. {question}
                </p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {SCALE_LABELS.map((label, li) => {
                    const value = li + 1;
                    const selected = answers[qi] === value;
                    return (
                      <button
                        key={value}
                        type="button"
                        onClick={() => setAnswers((prev) => prev.map((a, i) => (i === qi ? value : a)))}
                        className={`rounded-lg border px-2.5 py-1.5 text-xs transition ${
                          selected
                            ? "border-brand/60 bg-brand/10 text-brand dark:text-brand-dim"
                            : "border-black/10 dark:border-white/15 text-ink/60 dark:text-ink-dark/60 hover:bg-black/5 dark:hover:bg-white/10"
                        }`}
                      >
                        {label}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}

            {error && <p className="rounded-lg bg-red-500/10 px-3 py-2 text-xs text-red-600 dark:text-red-400">{error}</p>}

            <div className="border-t border-black/5 dark:border-white/10 pt-4">
              <Button onClick={submit} disabled={!allAnswered || submitting}>
                {submitting ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
                {submitting ? "Sending..." : "Submit answers"}
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </>
  );
}

// Floating "you've got a survey" nudge for any customer-facing page —
// fetches its own pending surveys so it can be dropped in with no prop
// wiring. Mounted on both the TicketTrident and Nykaa Pulse customer views
// (see SurveyPage.jsx and NykaaCatalogPage.jsx) since a PM's surveys are
// sent to every customer account regardless of which mega-tab they browse.
export function PendingSurveyNudge() {
  const [pendingSurveys, setPendingSurveys] = useState([]);
  const [loaded, setLoaded] = useState(false);

  function load() {
    api.pendingSurveys().then((r) => {
      setPendingSurveys(r.surveys);
      setLoaded(true);
    });
  }

  useEffect(() => {
    load();
  }, []);

  if (!loaded || pendingSurveys.length === 0) return null;
  return <PendingSurveyCard survey={pendingSurveys[0]} onAnswered={load} />;
}
