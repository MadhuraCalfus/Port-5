import { useState } from "react";
import { Check, Loader2, MessageSquareWarning, Send, X } from "lucide-react";
import { api } from "../../../api";
import { StarInput } from "./NykaaTicketChat";

// Real Nykaa has no channel for "the app itself is broken/slow/confusing" —
// only product reviews and order support. This floating widget is this
// app's stand-in for that gap: a rating plus a fixed set of app/webpage
// issue categories (not product-related, so no per-product theme list here
// the way FeedbackModal's product review has), a free-text box, and nothing
// else — deliberately not a chatbot. See nykaa_store.save_app_feedback /
// the PM-facing /nykaa/pm/app-feedback list.
const NEGATIVE_CATEGORIES = [
  "Page Not Loading",
  "Slow Performance",
  "Checkout / Payment Issue",
  "Broken Button or Link",
  "Confusing Navigation / Layout",
  "Login / Account Issue",
  "Other",
];

const POSITIVE_CATEGORIES = [
  "Easy to Use",
  "Fast Performance",
  "Smooth Checkout",
  "Great Design",
  "Found What I Needed",
  "Other",
];

export function NykaaAppFeedbackWidget() {
  const [open, setOpen] = useState(false);
  const [rating, setRating] = useState(null);
  const [categories, setCategories] = useState([]);
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [submitted, setSubmitted] = useState(false);

  function handleRatingChange(r) {
    setRating(r);
    setCategories([]);
  }

  function toggleCategory(c) {
    setCategories((prev) => (prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c]));
  }

  function reset() {
    setRating(null);
    setCategories([]);
    setDescription("");
    setError(null);
    setSubmitted(false);
  }

  function handleToggle() {
    if (open) reset();
    setOpen((o) => !o);
  }

  async function submit() {
    setSubmitting(true);
    setError(null);
    try {
      await api.nykaaSubmitAppFeedback({
        rating,
        categories: categories.length ? categories : ["Other"],
        description: description.trim() || null,
      });
      setSubmitted(true);
      setTimeout(() => {
        setOpen(false);
        reset();
      }, 1600);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={handleToggle}
        aria-label={open ? "Close app feedback" : "Rate this app / report an issue"}
        className="fixed bottom-5 right-5 z-40 grid h-14 w-14 place-items-center rounded-full bg-brand text-white shadow-lg shadow-brand/30 transition hover:opacity-90 active:scale-95"
      >
        {open ? <X size={22} /> : <MessageSquareWarning size={22} />}
      </button>

      {open && (
        <div className="fixed bottom-24 right-5 z-40 flex max-h-[75vh] w-80 flex-col overflow-hidden rounded-2xl border border-black/8 dark:border-white/10 bg-surface dark:bg-surface-dark shadow-xl">
          <div className="flex shrink-0 items-center gap-2.5 bg-brand px-4 py-3.5 text-white">
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-white/20">
              <MessageSquareWarning size={16} />
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold">Rate this app</p>
              <p className="truncate text-[11px] text-white/80">Report a bug or share feedback about the site</p>
            </div>
          </div>

          <div className="thin-scroll flex-1 overflow-y-auto p-4">
            {submitted ? (
              <div className="flex flex-col items-center gap-2 py-8 text-center">
                <span className="grid h-10 w-10 place-items-center rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
                  <Check size={20} />
                </span>
                <p className="text-sm font-medium text-ink dark:text-ink-dark">Thanks — we've logged this.</p>
              </div>
            ) : (
              <>
                <div className="flex flex-col items-center gap-1.5 border-b border-black/5 dark:border-white/10 pb-4">
                  <StarInput value={rating} onChange={handleRatingChange} size={24} />
                  <p className="text-xs text-ink/60 dark:text-ink-dark/60">
                    {rating ? `You're rating this app ${rating}★` : "How's your experience with the app?"}
                  </p>
                </div>

                {rating != null && (
                  <div className="mt-4 space-y-3">
                    <h4 className="text-sm font-semibold text-ink dark:text-ink-dark">
                      {rating <= 2 ? "What went wrong? (pick any that apply)" : "Anything to share? (pick any that apply)"}
                    </h4>
                    <div className="flex flex-wrap gap-2">
                      {(rating <= 2 ? NEGATIVE_CATEGORIES : POSITIVE_CATEGORIES).map((c) => (
                        <button
                          key={c}
                          type="button"
                          onClick={() => toggleCategory(c)}
                          className={`rounded-full border px-3 py-1.5 text-xs font-medium transition ${
                            categories.includes(c)
                              ? "border-brand bg-brand text-white"
                              : "border-black/10 dark:border-white/15 text-ink/70 dark:text-ink-dark/70 hover:bg-black/5 dark:hover:bg-white/10"
                          }`}
                        >
                          {c}
                        </button>
                      ))}
                    </div>
                    <textarea
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      rows={3}
                      placeholder="Describe the issue or your feedback (optional)"
                      className="w-full resize-none rounded-lg border border-black/10 dark:border-white/15 bg-transparent px-3 py-2 text-sm text-ink dark:text-ink-dark"
                    />
                  </div>
                )}

                {error && <p className="mt-3 rounded-lg bg-red-500/10 px-3 py-2 text-xs text-red-600 dark:text-red-400">{error}</p>}

                <button
                  type="button"
                  onClick={submit}
                  disabled={rating == null || submitting}
                  className="mt-4 flex w-full items-center justify-center gap-1.5 rounded-lg bg-brand px-3 py-2.5 text-sm font-semibold text-white transition disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {submitting ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
                  {submitting ? "Submitting..." : rating == null ? "Tap a star to continue" : "Submit"}
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}
