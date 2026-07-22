import { useState } from "react";
import { Loader2, MessageSquareText, Send, Star } from "lucide-react";
import { api } from "../../api";
import { Button, Card } from "../../components/primitives";

const RATING_LABELS = { 1: "Very unhappy", 2: "Unhappy", 3: "Okay", 4: "Happy", 5: "Very happy" };

export function SurveyPage() {
  const [rating, setRating] = useState(null);
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [submitted, setSubmitted] = useState(false);

  async function submit() {
    if (!rating) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.submitSurvey(rating, comment.trim());
      setSubmitted(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  }

  function startOver() {
    setRating(null);
    setComment("");
    setSubmitted(false);
    setError(null);
  }

  return (
    <div className="mx-auto max-w-xl">
      <Card className="p-6">
        {submitted ? (
          <>
            <h2 className="font-display text-lg font-semibold">Thanks for the feedback!</h2>
            <p className="mt-1.5 text-sm leading-relaxed text-ink/60 dark:text-ink-dark/60">
              It helps us understand what's working and what isn't — no ticket or follow-up needed.
            </p>
            <Button className="mt-5" variant="ghost" onClick={startOver}>
              Share more feedback
            </Button>
          </>
        ) : (
          <>
            <h2 className="font-display text-lg font-semibold">How's your experience been?</h2>
            <p className="mt-1.5 text-sm leading-relaxed text-ink/60 dark:text-ink-dark/60">
              A quick rating helps us spot trends — a comment helps us understand why.
            </p>

            <div className="mt-5 flex items-center justify-center gap-2">
              {[1, 2, 3, 4, 5].map((n) => (
                <button
                  key={n}
                  type="button"
                  onClick={() => setRating(n)}
                  aria-label={RATING_LABELS[n]}
                  className="grid h-11 w-11 place-items-center rounded-full transition hover:bg-black/5 dark:hover:bg-white/10"
                >
                  <Star
                    size={26}
                    className={rating && n <= rating ? "fill-amber-400 text-amber-400" : "text-ink/25 dark:text-ink-dark/25"}
                  />
                </button>
              ))}
            </div>
            {rating && (
              <p className="mt-1 text-center text-xs font-medium text-ink/60 dark:text-ink-dark/60">{RATING_LABELS[rating]}</p>
            )}

            <label className="mt-5 block text-xs text-ink/70 dark:text-ink-dark/70">
              <span className="mb-1.5 flex items-center gap-1.5">
                <MessageSquareText size={13} /> Anything you'd like to add? (optional)
              </span>
              <textarea
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                placeholder="Tell us more..."
                rows={4}
                className="w-full resize-none rounded-xl border border-black/10 dark:border-white/15 bg-black/[0.02] dark:bg-white/[0.03] p-3.5 text-sm outline-none focus:border-brand/60 focus:ring-2 focus:ring-brand/20"
              />
            </label>

            <div className="mt-5 flex items-center gap-3 border-t border-black/5 dark:border-white/10 pt-4">
              <Button onClick={submit} disabled={!rating || submitting}>
                {submitting ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
                {submitting ? "Sending..." : "Send feedback"}
              </Button>
            </div>

            {error && <p className="mt-3 rounded-lg bg-red-500/10 px-3 py-2 text-xs text-red-600 dark:text-red-400">{error}</p>}
          </>
        )}
      </Card>
    </div>
  );
}
