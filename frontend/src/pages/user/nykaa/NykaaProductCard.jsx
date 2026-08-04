import { useEffect, useState } from "react";
import clsx from "clsx";
import { ChevronDown, ChevronUp, Loader2, Minus, Plus, Send, ShoppingBag, Sparkles, Star } from "lucide-react";
import { api } from "../../../api";
import { Button, Card } from "../../../components/primitives";

// Shared by NykaaCatalogPage (the shop grid) and NykaaBeautyProfilePage (the
// "Recommended for you" grid) — split into its own module so the two pages
// can import each other's exports (this one, ProductCard) without a circular
// import between them.

export function formatInr(amount) {
  return `₹${Number(amount).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

// There's no real product photography in this dataset — a colored tile
// with a category-appropriate icon stands in for a photo, consistently,
// rather than a broken <img> or nothing at all.
const CATEGORY_VISUAL = {
  Makeup: { icon: "💄", gradient: "from-pink-300/50 to-rose-200/40" },
  Skincare: { icon: "🧴", gradient: "from-emerald-300/50 to-teal-200/40" },
  "Hair Care": { icon: "💇", gradient: "from-amber-300/50 to-orange-200/40" },
  "Bath & Body": { icon: "🧼", gradient: "from-sky-300/50 to-cyan-200/40" },
  Fragrance: { icon: "🌸", gradient: "from-fuchsia-300/50 to-pink-200/40" },
  "Men's Grooming": { icon: "🪒", gradient: "from-slate-300/50 to-blue-200/40" },
  "Beauty Tools": { icon: "🪞", gradient: "from-violet-300/50 to-purple-200/40" },
  Wellness: { icon: "🌿", gradient: "from-lime-300/50 to-green-200/40" },
  "Personal Care": { icon: "🧽", gradient: "from-indigo-300/50 to-blue-200/40" },
  "Nail Care": { icon: "💅", gradient: "from-rose-300/50 to-red-200/40" },
};
const DEFAULT_VISUAL = { icon: "✨", gradient: "from-brand/30 to-brand/10" };

function ProductImage({ categoryName }) {
  const visual = CATEGORY_VISUAL[categoryName] ?? DEFAULT_VISUAL;
  return (
    <div className={clsx("grid h-28 place-items-center rounded-xl bg-gradient-to-br text-4xl", visual.gradient)}>
      {visual.icon}
    </div>
  );
}

// One published review, tagged (when the reviewer has a Beauty Portfolio)
// with a "someone with my skin type" badge — the core Beauty Portfolio
// value prop. Reviewers without a profile just show no badge, never an
// empty placeholder one.
function ReviewRow({ review }) {
  return (
    <div className="border-t border-black/5 dark:border-white/10 pt-2 first:border-t-0 first:pt-0">
      <div className="flex items-center justify-between gap-2">
        {review.rating != null && (
          <div className="flex items-center gap-0.5">
            {[1, 2, 3, 4, 5].map((n) => (
              <Star
                key={n}
                size={11}
                className={n <= review.rating ? "fill-amber-400 text-amber-400" : "text-ink/20 dark:text-ink-dark/20"}
              />
            ))}
          </div>
        )}
        <span className="text-[10px] text-ink/40 dark:text-ink-dark/40">
          {new Date(review.created_at).toLocaleDateString()}
        </span>
      </div>
      {review.review_title && (
        <p className="mt-1 text-[11px] font-semibold text-ink dark:text-ink-dark">{review.review_title}</p>
      )}
      {review.review_description && (
        <p className="mt-0.5 text-[11px] leading-relaxed text-ink/60 dark:text-ink-dark/60">
          {review.review_description}
        </p>
      )}
      {(review.skin_type || review.hair_type) && (
        <div className="mt-1.5 flex flex-wrap gap-1">
          {review.skin_type && (
            <span className="rounded-full bg-brand/10 px-2 py-0.5 text-[10px] font-medium text-brand dark:text-brand-dim">
              {review.skin_type} skin
            </span>
          )}
          {review.hair_type && (
            <span className="rounded-full bg-brand/10 px-2 py-0.5 text-[10px] font-medium text-brand dark:text-brand-dim">
              {review.hair_type} hair
            </span>
          )}
        </div>
      )}
    </div>
  );
}

// Phase 4 "what customers say" + "ask the reviews" — collapsed by default so
// browsing the grid never fires an LLM call per product; the summary is
// fetched once, the first time this panel is expanded, and cached in this
// component's own state for the rest of the session (re-collapsing and
// re-expanding the same card in the same page load won't refetch).
function WhatCustomersSay({ productId, visible }) {
  const [summary, setSummary] = useState(null);
  const [loadingSummary, setLoadingSummary] = useState(false);
  const [summaryError, setSummaryError] = useState(null);

  // "Recent reviews" — same lazy-on-first-expand pattern as the summary
  // fetch below, its own independent request/cache so a slow reviews fetch
  // never blocks the summary (or vice versa).
  const [reviews, setReviews] = useState(null);
  const [loadingReviews, setLoadingReviews] = useState(false);
  const [reviewsError, setReviewsError] = useState(null);

  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [askError, setAskError] = useState(null);
  // Local-only history of this card's Q&A, per the spec — no need to persist
  // across reloads, just enough so a shopper can ask more than one question
  // and still see earlier answers while the card stays expanded.
  const [history, setHistory] = useState([]);

  // Gated on `visible` (not just mount) because the parent always renders
  // this component now, rather than conditionally including it in JSX —
  // that's what lets `summary`/`history` survive a collapse/re-expand
  // instead of being wiped by an unmount. Fetching only fires the first
  // time this card is actually expanded, never on initial page load.
  useEffect(() => {
    if (!visible || summary || loadingSummary) return;
    setLoadingSummary(true);
    setSummaryError(null);
    api
      .nykaaProductSummary(productId)
      .then(setSummary)
      .catch((e) => setSummaryError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoadingSummary(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible, productId]);

  useEffect(() => {
    if (!visible || reviews || loadingReviews) return;
    setLoadingReviews(true);
    setReviewsError(null);
    api
      .nykaaProductReviews(productId)
      .then((r) => setReviews(r.reviews))
      .catch((e) => setReviewsError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoadingReviews(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible, productId]);

  if (!visible) return null;

  async function submitQuestion(e) {
    e.preventDefault();
    const q = question.trim();
    if (!q || asking) return;
    setAsking(true);
    setAskError(null);
    try {
      const r = await api.nykaaAskReviews(productId, q);
      setHistory((prev) => [...prev, { question: q, ...r }]);
      setQuestion("");
    } catch (e) {
      setAskError(e instanceof Error ? e.message : String(e));
    } finally {
      setAsking(false);
    }
  }

  return (
    <div className="mt-3 space-y-2.5 rounded-xl bg-black/[0.02] dark:bg-white/[0.03] p-3">
      {loadingSummary ? (
        <p className="flex items-center gap-1.5 text-xs text-ink/50 dark:text-ink-dark/50">
          <Loader2 size={12} className="animate-spin" /> Reading reviews...
        </p>
      ) : summaryError ? (
        <p className="text-xs text-red-600 dark:text-red-400">{summaryError}</p>
      ) : summary ? (
        <div>
          <p className="text-xs leading-relaxed text-ink/70 dark:text-ink-dark/70">{summary.summary}</p>
          {(summary.fit_notes?.length ?? 0) > 0 && (
            <div className="mt-2 rounded-lg bg-brand/10 px-2.5 py-2 ring-1 ring-brand/15">
              <p className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-brand dark:text-brand-dim">
                <Sparkles size={11} /> Will this suit you?
              </p>
              <ul className="mt-1 space-y-1">
                {summary.fit_notes.map((note, i) => (
                  <li key={i} className="text-[11px] leading-relaxed text-ink/80 dark:text-ink-dark/80">
                    {note}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {((summary.praise_points?.length ?? 0) > 0 || (summary.concern_points?.length ?? 0) > 0) && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {(summary.praise_points || []).map((p, i) => (
                <span
                  key={`praise-${i}`}
                  className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium text-emerald-600 dark:text-emerald-400"
                >
                  {p}
                </span>
              ))}
              {(summary.concern_points || []).map((c, i) => (
                <span
                  key={`concern-${i}`}
                  className="rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium text-amber-600 dark:text-amber-400"
                >
                  {c}
                </span>
              ))}
            </div>
          )}
        </div>
      ) : null}

      <div className="border-t border-black/5 dark:border-white/10 pt-2">
        <p className="text-[10px] font-semibold uppercase tracking-wide text-ink/40 dark:text-ink-dark/40">
          Recent reviews
        </p>
        {loadingReviews ? (
          <p className="mt-1.5 flex items-center gap-1.5 text-xs text-ink/50 dark:text-ink-dark/50">
            <Loader2 size={12} className="animate-spin" /> Loading reviews...
          </p>
        ) : reviewsError ? (
          <p className="mt-1.5 text-xs text-red-600 dark:text-red-400">{reviewsError}</p>
        ) : reviews && reviews.length === 0 ? (
          <p className="mt-1.5 text-xs text-ink/50 dark:text-ink-dark/50">No published reviews yet.</p>
        ) : reviews ? (
          <div className="mt-1.5 max-h-56 space-y-2 overflow-y-auto pr-1">
            {reviews.map((r) => (
              <ReviewRow key={r.id} review={r} />
            ))}
          </div>
        ) : null}
      </div>

      {history.length > 0 && (
        <div className="space-y-2 border-t border-black/5 dark:border-white/10 pt-2">
          {history.map((h, i) => (
            <div key={i}>
              <p className="text-[11px] font-medium text-ink dark:text-ink-dark">Q: {h.question}</p>
              <p
                className={clsx(
                  "mt-0.5 rounded-lg px-2.5 py-1.5 text-[11px] leading-relaxed",
                  h.grounded
                    ? "bg-black/[0.03] dark:bg-white/[0.05] text-ink/70 dark:text-ink-dark/70"
                    : "border border-dashed border-black/15 dark:border-white/20 text-ink/50 dark:text-ink-dark/50",
                )}
              >
                {h.answer}
              </p>
            </div>
          ))}
        </div>
      )}

      <form onSubmit={submitQuestion} className="flex items-center gap-1.5">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask about this product..."
          className="w-0 flex-1 rounded-lg border border-black/10 dark:border-white/15 bg-transparent px-2.5 py-1.5 text-xs text-ink dark:text-ink-dark placeholder:text-ink/40 dark:placeholder:text-ink-dark/40 outline-none focus:border-brand/60"
        />
        <Button type="submit" className="shrink-0 px-2.5 py-1.5 text-xs" disabled={asking || !question.trim()}>
          {asking ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} />}
        </Button>
      </form>
      {askError && <p className="text-[11px] text-red-600 dark:text-red-400">{askError}</p>}
    </div>
  );
}

export function ProductCard({ product, quantity, onQuantityChange, onAdd }) {
  const detailTags = Object.entries(product.details || {}).slice(0, 2);
  const [expanded, setExpanded] = useState(false);
  return (
    <Card className="flex flex-col p-4">
      <ProductImage categoryName={product.category_name} />

      <div className="mt-3 flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="truncate text-sm font-semibold text-ink dark:text-ink-dark">{product.name}</h3>
          <p className="text-xs text-ink/50 dark:text-ink-dark/50">{product.brand_name}</p>
        </div>
        <span className="shrink-0 text-sm font-semibold text-brand dark:text-brand-dim">
          {formatInr(product.price_inr)}
        </span>
      </div>

      <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-ink/60 dark:text-ink-dark/60">
        {product.description}
      </p>

      <div className="mt-2 flex flex-wrap gap-1.5">
        <span className="rounded-full bg-brand/10 px-2 py-0.5 text-[10px] font-medium text-brand dark:text-brand-dim">
          {product.category_name}
        </span>
        {detailTags.map(([key, value]) => (
          <span
            key={key}
            className="rounded-full bg-black/5 dark:bg-white/10 px-2 py-0.5 text-[10px] text-ink/60 dark:text-ink-dark/60"
          >
            {key}: {String(value)}
          </span>
        ))}
      </div>

      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="mt-3 flex items-center gap-1 self-start text-[11px] font-medium text-brand dark:text-brand-dim hover:underline"
      >
        <Sparkles size={12} /> What customers say {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
      </button>
      <WhatCustomersSay productId={product.id} visible={expanded} />

      <div className="mt-auto flex items-center justify-between gap-2 border-t border-black/5 dark:border-white/10 pt-3">
        <div className="flex items-center gap-1 rounded-lg border border-black/10 dark:border-white/15">
          <button
            type="button"
            onClick={() => onQuantityChange(Math.max(1, quantity - 1))}
            className="grid h-7 w-7 place-items-center text-ink/60 dark:text-ink-dark/60 hover:bg-black/5 dark:hover:bg-white/10"
            aria-label="Decrease quantity"
          >
            <Minus size={13} />
          </button>
          <span className="w-6 text-center text-xs font-medium tabular-nums">{quantity}</span>
          <button
            type="button"
            onClick={() => onQuantityChange(quantity + 1)}
            className="grid h-7 w-7 place-items-center text-ink/60 dark:text-ink-dark/60 hover:bg-black/5 dark:hover:bg-white/10"
            aria-label="Increase quantity"
          >
            <Plus size={13} />
          </button>
        </div>
        <Button onClick={() => onAdd(quantity)} className="px-3 py-1.5 text-xs">
          <ShoppingBag size={13} /> Add
        </Button>
      </div>
    </Card>
  );
}
