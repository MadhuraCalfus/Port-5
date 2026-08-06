import { useEffect, useRef, useState } from "react";
import { AlertTriangle, ImagePlus, Loader2, MessageCircle, RefreshCw, Send, ShieldQuestion, Sparkles, Star } from "lucide-react";
import { api } from "../../../api";
import { Button, Card, Modal } from "../../../components/primitives";
import { StarInput, TicketChatModal } from "./NykaaTicketChat";
import { ProductImage } from "./NykaaProductCard";

const MAX_REVIEW_PHOTO_BYTES = 5 * 1024 * 1024;

function formatInr(amount) {
  return `₹${Number(amount).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

// "Show off your look!" — an optional photo attached to a review. Before
// upload (or once has_photo but not yet fetched), shows the add-photo
// button; once a photo exists server-side, fetches it as an authenticated
// blob and renders it as a thumbnail (see api.nykaaReviewPhotoUrl — a plain
// <img src> can't carry the Authorization header this endpoint requires).
function ReviewPhotoField({ order, item }) {
  const [hasPhoto, setHasPhoto] = useState(Boolean(item.has_photo));
  const [photoUrl, setPhotoUrl] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    if (!hasPhoto) return undefined;
    let cancelled = false;
    let objectUrl = null;
    api
      .nykaaReviewPhotoUrl(order.id, item.id)
      .then((url) => {
        if (cancelled) {
          URL.revokeObjectURL(url);
          return;
        }
        objectUrl = url;
        setPhotoUrl(url);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [hasPhoto, order.id, item.id]);

  async function handleFile(e) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (file.size > MAX_REVIEW_PHOTO_BYTES) {
      setError("That photo is too large (max 5MB).");
      return;
    }
    setUploading(true);
    setError(null);
    try {
      await api.nykaaUploadReviewPhoto(order.id, item.id, file);
      setHasPhoto(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="mt-2">
      <label className="mb-1 block text-[11px] text-ink/60 dark:text-ink-dark/60">Show off your look! (optional)</label>
      {hasPhoto ? (
        photoUrl ? (
          <img
            src={photoUrl}
            alt="Your review"
            className="h-16 w-16 rounded-lg border border-black/10 dark:border-white/15 object-cover"
          />
        ) : (
          <div className="grid h-16 w-16 place-items-center rounded-lg bg-black/5 dark:bg-white/10">
            <Loader2 size={14} className="animate-spin text-ink/40 dark:text-ink-dark/40" />
          </div>
        )
      ) : (
        <>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/png,image/gif,image/webp"
            onChange={handleFile}
            className="hidden"
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="inline-flex items-center gap-1.5 rounded-lg bg-black/5 dark:bg-white/10 px-2.5 py-1.5 text-xs font-medium text-ink/70 dark:text-ink-dark/70 hover:bg-black/10 dark:hover:bg-white/15 disabled:opacity-40"
          >
            {uploading ? <Loader2 size={13} className="animate-spin" /> : <ImagePlus size={13} />}
            {uploading ? "Uploading..." : "Add a photo"}
          </button>
        </>
      )}
      {error && <p className="mt-1 text-[11px] text-red-600 dark:text-red-400">{error}</p>}
    </div>
  );
}

// Compact list row — just enough to identify the item and act on it. The
// full rating/review/photo composer lives in FeedbackModal, and raising a
// ticket opens TicketChatModal — both opened via these buttons rather than
// shown inline, matching the real Nykaa "Orders list -> tap in" flow.
// Left to right: Feedback (shows the item's own rating once set, rather than
// a separate star row next to it) -> Help (no ticket number/status — just a
// labeled way in, with a red unread-reply count when the other side has
// replied) — works identically whether or not a ticket exists yet, since
// TicketChatModal already branches on item.linked_ticket_id itself.
function OrderItemRow({ item, onOpenFeedback, onOpenTicketChat }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-black/5 dark:border-white/10 py-3 first:border-t-0 first:pt-0">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-ink dark:text-ink-dark">{item.product_name}</p>
        <p className="text-xs text-ink/50 dark:text-ink-dark/50">
          {item.quantity} × {formatInr(item.unit_price_at_purchase)}
        </p>
      </div>

      <div className="flex shrink-0 flex-wrap items-center gap-2">
        <Button variant="ghost" onClick={() => onOpenFeedback(item)} className="px-3 py-1.5 text-xs">
          <Star size={13} className={item.rating ? "fill-amber-400 text-amber-400" : ""} />
          {item.rating ? `${item.rating}/5` : "Feedback"}
        </Button>
        <button
          onClick={() => onOpenTicketChat(item)}
          aria-label="Get help with this item"
          className="relative inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-ink/60 dark:text-ink-dark/60 hover:bg-black/5 dark:hover:bg-white/10"
        >
          <MessageCircle size={14} /> Help
          {item.unread_comments > 0 && (
            <span className="absolute -right-1.5 -top-1.5 grid h-4 min-w-[16px] place-items-center rounded-full bg-red-500 px-1 text-[10px] font-semibold leading-none text-white">
              {item.unread_comments}
            </span>
          )}
        </button>
      </div>
    </div>
  );
}

// TicketChatModal (the "Help" chat) now lives in NykaaTicketChat.jsx, shared
// with the floating chatbot — imported below rather than defined here.

// A single toggleable pill — the building block for the "what did/didn't
// you like" theme picker below. Selected state is the only thing that
// differs from a plain filter chip elsewhere in this app.
function ThemeChip({ label, selected, onToggle }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className={`rounded-full border px-3 py-1.5 text-xs font-medium transition ${
        selected
          ? "border-brand bg-brand text-white"
          : "border-black/10 dark:border-white/15 text-ink/70 dark:text-ink-dark/70 hover:bg-black/5 dark:hover:bg-white/10"
      }`}
    >
      {label}
    </button>
  );
}

// The "Feedback" detail screen — product context, then a star rating first
// and *only once a star is tapped* does the rest reveal itself: which
// question to ask ("what didn't you like" vs "what did you like") and which
// chips to offer both depend on the star value, and the chips themselves
// come straight from this exact product's own seeded positive/negative
// themes (product.positive_themes / negative_themes) rather than a generic
// fixed list — so the options a customer sees are always about the thing
// they actually bought. A free-text "anything else" box and the photo
// field cover whatever the fixed chips don't. Opened from a compact
// order-item row rather than always shown inline.
function FeedbackModal({ order, item, onClose, onChanged, onReviewSubmitted }) {
  const [product, setProduct] = useState(null);
  const [rating, setRating] = useState(item.rating);
  const [selectedThemes, setSelectedThemes] = useState([]);
  const [otherText, setOtherText] = useState(item.review_description ?? "");
  const [title, setTitle] = useState(item.review_title ?? "");
  const [generatingTitle, setGeneratingTitle] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [autoTicketId, setAutoTicketId] = useState(null);
  const [submitted, setSubmitted] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .nykaaGetProduct(item.product_id)
      .then((p) => !cancelled && setProduct(p))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [item.product_id]);

  const isNegative = rating != null && rating <= 2;
  const themeOptions = rating == null ? [] : isNegative ? product?.negative_themes ?? [] : product?.positive_themes ?? [];

  // Changing the star rating across the negative/positive line (e.g. 2 -> 4)
  // clears whatever was picked under the old question — those chips no
  // longer apply once the question itself has changed.
  function handleRating(value) {
    setRating((prev) => {
      const prevIsNegative = prev != null && prev <= 2;
      const nextIsNegative = value != null && value <= 2;
      if (prevIsNegative !== nextIsNegative) setSelectedThemes([]);
      return value;
    });
  }

  function toggleTheme(theme) {
    setSelectedThemes((prev) => (prev.includes(theme) ? prev.filter((t) => t !== theme) : [...prev, theme]));
  }

  function buildDescription() {
    const lead = selectedThemes.length > 0 ? `${isNegative ? "Didn't like" : "Liked"}: ${selectedThemes.join(", ")}` : null;
    const other = otherText.trim() || null;
    return [lead, other].filter(Boolean).join(". ") || null;
  }

  async function generateTitle() {
    const description = buildDescription();
    if (!description) return;
    setGeneratingTitle(true);
    setError(null);
    try {
      const r = await api.nykaaGenerateReviewTitle(description);
      setTitle(r.title);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setGeneratingTitle(false);
    }
  }

  async function submitReview() {
    setSubmitting(true);
    setError(null);
    try {
      const description = buildDescription();
      const { auto_ticket_id, ...updated } = await api.nykaaSubmitReview(order.id, item.id, {
        rating: rating ?? null,
        // Left blank on purpose when the customer didn't write one: the
        // backend generates one automatically from the description.
        title: title.trim() || null,
        description,
      });
      onChanged(updated);
      onReviewSubmitted?.();
      if (auto_ticket_id) setAutoTicketId(auto_ticket_id);
      setSubmitted(true);
      setTimeout(onClose, 1400);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  }

  const detailChips = product ? Object.values(product.details ?? {}).filter(Boolean).slice(0, 3) : [];

  return (
    <Modal title="Rate & Review" onClose={onClose}>
      <div className="flex gap-3 border-b border-black/5 dark:border-white/10 pb-4">
        <div className="w-16 shrink-0">
          <ProductImage categoryName={product?.category_name} size="h-16" />
        </div>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-ink dark:text-ink-dark">{item.product_name}</p>
          <p className="mt-0.5 line-clamp-2 text-xs text-ink/60 dark:text-ink-dark/60">
            {product?.description ?? item.product_description}
          </p>
          {detailChips.length > 0 && (
            <p className="mt-1.5 text-xs text-ink/50 dark:text-ink-dark/50">{detailChips.join(" | ")}</p>
          )}
        </div>
      </div>

      <div className="flex flex-col items-center gap-1.5 border-b border-black/5 dark:border-white/10 py-4">
        <StarInput value={rating} onChange={handleRating} size={26} />
        <p className="text-xs text-ink/60 dark:text-ink-dark/60">
          {rating ? `You are rating this product ${rating}★` : "Tap a star to rate"}
        </p>
      </div>

      {rating != null && (
        <div className="mt-4 space-y-3">
          <h4 className="text-sm font-semibold text-ink dark:text-ink-dark">
            {isNegative ? "What didn't you like?" : "What did you like?"}
          </h4>
          {themeOptions.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {themeOptions.map((theme) => (
                <ThemeChip key={theme} label={theme} selected={selectedThemes.includes(theme)} onToggle={() => toggleTheme(theme)} />
              ))}
            </div>
          ) : (
            <p className="text-xs text-ink/40 dark:text-ink-dark/40">Loading options for this product...</p>
          )}

          <label className="block text-xs text-ink/60 dark:text-ink-dark/60">
            Anything else? (optional)
            <textarea
              value={otherText}
              onChange={(e) => setOtherText(e.target.value)}
              rows={3}
              placeholder={isNegative ? "Tell us more about what went wrong..." : "Tell us more about what you loved..."}
              className="mt-1 w-full resize-none rounded-lg border border-black/10 dark:border-white/15 bg-transparent px-3 py-2 text-sm text-ink dark:text-ink-dark"
            />
          </label>

          <label className="block text-xs text-ink/60 dark:text-ink-dark/60">
            Review title (optional — we'll write one if you leave it blank)
            <div className="mt-1 flex items-center gap-1.5">
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Great for sensitive skin"
                className="w-full rounded-lg border border-black/10 dark:border-white/15 bg-transparent px-3 py-2 text-sm text-ink dark:text-ink-dark outline-none focus:border-brand/60"
              />
              <button
                type="button"
                onClick={generateTitle}
                disabled={generatingTitle || (selectedThemes.length === 0 && !otherText.trim())}
                title="Generate a title from what you picked/wrote above"
                className="flex shrink-0 items-center gap-1 rounded-lg border border-black/10 dark:border-white/15 px-2.5 py-2 text-xs font-medium text-ink/70 dark:text-ink-dark/70 hover:bg-black/5 dark:hover:bg-white/10 disabled:opacity-40"
              >
                {generatingTitle ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />}
                Generate
              </button>
            </div>
          </label>

          <ReviewPhotoField order={order} item={item} />
        </div>
      )}

      {error && <p className="mt-3 rounded-lg bg-red-500/10 px-3 py-2 text-xs text-red-600 dark:text-red-400">{error}</p>}

      {autoTicketId && (
        <p className="mt-3 flex items-center gap-1.5 rounded-lg bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-400">
          <AlertTriangle size={13} />
          We noticed this sounds like a real issue — ticket #{autoTicketId} was opened for you automatically.
        </p>
      )}

      {submitted ? (
        <p className="mt-4 rounded-xl bg-emerald-500/10 px-3 py-3 text-center text-sm font-medium text-emerald-600 dark:text-emerald-400">
          Thanks for your feedback!
        </p>
      ) : (
        <Button onClick={submitReview} disabled={submitting || rating == null} className="mt-4 w-full">
          {submitting ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
          {submitting ? "Submitting..." : rating == null ? "Tap a star to continue" : "Submit"}
        </Button>
      )}
    </Modal>
  );
}

// Opened via the order header's "Delivery Feedback" button (or the rated
// badge, to review what was submitted) rather than an always-expanded
// inline widget — a 5-star scale, matching every other rating surface in
// Nykaa Pulse, instead of the old 0-10 numeric scale.
function DeliveryFeedbackModal({ order, onClose, onChanged }) {
  const [rating, setRating] = useState(order.delivery_rating ?? null);
  const [compliment, setCompliment] = useState(order.delivery_compliment ?? "");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [submitted, setSubmitted] = useState(false);

  async function submit() {
    if (rating == null) return;
    setSubmitting(true);
    setError(null);
    try {
      const updated = await api.nykaaSubmitDeliveryRating(order.id, {
        rating,
        compliment: compliment.trim() || null,
      });
      onChanged(updated);
      setSubmitted(true);
      setTimeout(onClose, 1200);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal title="Delivery Feedback" onClose={onClose}>
      <p className="text-xs text-ink/60 dark:text-ink-dark/60">Order #{order.id}</p>

      <div className="flex flex-col items-center gap-1.5 border-b border-black/5 dark:border-white/10 py-4">
        <StarInput value={rating} onChange={setRating} size={26} />
        <p className="text-xs text-ink/60 dark:text-ink-dark/60">
          {rating ? `You are rating this delivery ${rating}★` : "Tap a star to rate your delivery"}
        </p>
      </div>

      <label className="mt-4 block text-xs text-ink/60 dark:text-ink-dark/60">
        Your review (optional)
        <textarea
          value={compliment}
          onChange={(e) => setCompliment(e.target.value)}
          rows={3}
          placeholder="Anything to say about the delivery?"
          className="mt-1 w-full resize-none rounded-lg border border-black/10 dark:border-white/15 bg-transparent px-3 py-2 text-sm text-ink dark:text-ink-dark"
        />
      </label>

      {error && <p className="mt-3 rounded-lg bg-red-500/10 px-3 py-2 text-xs text-red-600 dark:text-red-400">{error}</p>}

      {submitted ? (
        <p className="mt-4 rounded-xl bg-emerald-500/10 px-3 py-3 text-center text-sm font-medium text-emerald-600 dark:text-emerald-400">
          Thanks for your feedback!
        </p>
      ) : (
        <Button onClick={submit} disabled={rating == null || submitting} className="mt-4 w-full">
          {submitting ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
          {submitting ? "Submitting..." : "Submit"}
        </Button>
      )}
    </Modal>
  );
}

// Real Nykaa's own post-review flow: right after a review is submitted, if
// the customer doesn't have a Beauty Portfolio yet, nudge them to set one
// up — framed as helping other shoppers see reviews from people like them,
// not as "please fill out this form." "Skip for now" just hides it for the
// rest of the session; nothing is persisted server-side for a dismiss.
function BeautyProfileNudge({ onGoToProfile, onDismiss }) {
  return (
    <Card className="flex flex-wrap items-center justify-between gap-3 border-brand/20 bg-brand/[0.06] p-4 dark:bg-brand/[0.1]">
      <div className="flex items-start gap-2.5">
        <span className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-full bg-brand/10 text-brand dark:text-brand-dim">
          <Sparkles size={15} />
        </span>
        <p className="text-xs leading-relaxed text-ink/70 dark:text-ink-dark/70">
          <span className="font-semibold text-ink dark:text-ink-dark">Want to help other shoppers?</span> Add your
          skin and hair type so they can see reviews from people like them.
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <Button onClick={onGoToProfile} className="px-3 py-1.5 text-xs">
          Let's go
        </Button>
        <Button variant="ghost" onClick={onDismiss} className="px-3 py-1.5 text-xs">
          Skip for now
        </Button>
      </div>
    </Card>
  );
}

export function NykaaOrdersPage({ onNavigateToBeautyProfile }) {
  const [orders, setOrders] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);

  // Beauty Portfolio post-review nudge: fetched once on mount (rather than
  // only lazily after a review), so by the time a review is actually
  // submitted we already know whether to offer it — no extra round trip in
  // the middle of the submit flow. showNudge only flips on once a review has
  // been submitted this session AND the profile is still entirely empty.
  const [beautyProfile, setBeautyProfile] = useState(null);
  const [showNudge, setShowNudge] = useState(false);
  const [nudgeDismissed, setNudgeDismissed] = useState(false);

  // { order, item } for whichever row's "Feedback" button was clicked, or
  // null when the modal is closed — one modal instance for the whole page
  // rather than one per row.
  const [activeFeedback, setActiveFeedback] = useState(null);
  // The order whose "Delivery Feedback" button was clicked, or null.
  const [activeDeliveryFeedback, setActiveDeliveryFeedback] = useState(null);
  // { order, item } for whichever row's "Raise a Ticket" button was clicked.
  const [activeTicketChat, setActiveTicketChat] = useState(null);

  function load() {
    setRefreshing(true);
    api
      .nykaaMyOrders()
      .then((r) => setOrders(r.orders))
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setRefreshing(false));
  }

  useEffect(() => {
    load();
    api.nykaaGetBeautyProfile().then(setBeautyProfile).catch(() => {});
  }, []);

  function isEmptyProfile(profile) {
    return Boolean(profile) && !profile.skin_type && !profile.hair_type && !profile.makeup_preferences;
  }

  function handleReviewSubmitted() {
    if (nudgeDismissed) return;
    if (beautyProfile) {
      if (isEmptyProfile(beautyProfile)) setShowNudge(true);
      return;
    }
    // Profile fetch hadn't resolved yet (unlikely, but possible) — check now
    // rather than skipping the nudge outright.
    api
      .nykaaGetBeautyProfile()
      .then((p) => {
        setBeautyProfile(p);
        if (isEmptyProfile(p)) setShowNudge(true);
      })
      .catch(() => {});
  }

  function patchOrder(orderId, patch) {
    setOrders((prev) => prev.map((o) => (o.id === orderId ? { ...o, ...patch } : o)));
  }

  function patchItem(orderId, updatedItem) {
    // Merge rather than replace: the review-submit response (nykaa_store's
    // _get_order_item) doesn't re-join product_name/description, so a full
    // replace would blank those out of the row after submitting a review.
    setOrders((prev) =>
      prev.map((o) =>
        o.id !== orderId ? o : { ...o, items: o.items.map((i) => (i.id === updatedItem.id ? { ...i, ...updatedItem } : i)) },
      ),
    );
  }

  const refreshButton = (
    <button
      onClick={load}
      disabled={refreshing}
      className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs text-ink/50 dark:text-ink-dark/50 hover:bg-black/5 dark:hover:bg-white/10 disabled:opacity-40"
    >
      <RefreshCw size={13} className={refreshing ? "animate-spin" : ""} /> Refresh
    </button>
  );

  if (error) {
    return <p className="rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-600 dark:text-red-400">{error}</p>;
  }

  if (orders === null) {
    return (
      <div className="flex items-center justify-center gap-2 py-10 text-sm text-ink/50 dark:text-ink-dark/50">
        <Loader2 size={16} className="animate-spin" /> Loading your orders...
      </div>
    );
  }

  if (orders.length === 0) {
    return (
      <div className="space-y-3">
        <div className="flex justify-end">{refreshButton}</div>
        <Card className="flex flex-col items-center gap-2 p-10 text-center">
          <ShieldQuestion size={28} className="text-ink/30 dark:text-ink-dark/30" />
          <p className="text-sm text-ink/60 dark:text-ink-dark/60">You haven't placed any Nykaa Pulse orders yet.</p>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">{refreshButton}</div>
      {showNudge && (
        <BeautyProfileNudge
          onGoToProfile={() => onNavigateToBeautyProfile?.()}
          onDismiss={() => {
            setShowNudge(false);
            setNudgeDismissed(true);
          }}
        />
      )}
      {orders.map((order) => (
        <Card key={order.id} className="p-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h3 className="font-display text-base font-semibold text-ink dark:text-ink-dark">Order #{order.id}</h3>
              <p className="text-xs text-ink/50 dark:text-ink-dark/50">{new Date(order.placed_at).toLocaleString()}</p>
            </div>
            <div className="flex items-center gap-2">
              {order.delivery_rating != null ? (
                <button
                  onClick={() => setActiveDeliveryFeedback(order)}
                  className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2.5 py-1 text-xs font-medium text-emerald-600 dark:text-emerald-400 hover:bg-emerald-500/20"
                >
                  <Star size={12} className="fill-current" /> {order.delivery_rating}/5
                </button>
              ) : (
                <Button variant="ghost" onClick={() => setActiveDeliveryFeedback(order)} className="px-3 py-1.5 text-xs">
                  <Star size={13} /> Delivery Feedback
                </Button>
              )}
              <span className="rounded-full bg-brand/10 px-2.5 py-1 text-xs font-semibold text-brand dark:text-brand-dim">
                {order.status}
              </span>
              <span className="text-sm font-semibold text-ink dark:text-ink-dark">{formatInr(order.total_amount)}</span>
            </div>
          </div>

          <div className="mt-2">
            {order.items.map((item) => (
              <OrderItemRow
                key={item.id}
                item={item}
                onOpenFeedback={(clickedItem) => setActiveFeedback({ order, item: clickedItem })}
                onOpenTicketChat={(clickedItem) => setActiveTicketChat({ order, item: clickedItem })}
              />
            ))}
          </div>
        </Card>
      ))}

      {activeFeedback && (
        <FeedbackModal
          order={activeFeedback.order}
          item={activeFeedback.item}
          onClose={() => setActiveFeedback(null)}
          onChanged={(updated) => patchItem(activeFeedback.order.id, updated)}
          onReviewSubmitted={handleReviewSubmitted}
        />
      )}

      {activeDeliveryFeedback && (
        <DeliveryFeedbackModal
          order={activeDeliveryFeedback}
          onClose={() => setActiveDeliveryFeedback(null)}
          onChanged={(updated) => patchOrder(activeDeliveryFeedback.id, updated)}
        />
      )}

      {activeTicketChat && (
        <TicketChatModal
          order={activeTicketChat.order}
          item={activeTicketChat.item}
          onClose={() => setActiveTicketChat(null)}
          onTicketRaised={(t) =>
            patchItem(activeTicketChat.order.id, { id: activeTicketChat.item.id, linked_ticket_id: t.id, ticket_status: t.status })
          }
        />
      )}
    </div>
  );
}
