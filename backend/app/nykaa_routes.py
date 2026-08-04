"""Nykaa Pulse — cosmetics catalog, ordering, review, and ticket-raising API.

A separate APIRouter (prefix /api/nykaa) rather than more handlers bolted
onto main.py, so this whole feature area stays physically additive — one
`app.include_router(nykaa_router)` line in main.py is the only touch point.

Reviews and tickets raised here run through the *same AI pipelines* as "My
Existing Project" (feedback_ai.analyze_feedback, classifier.build_ticket_
result) but persist into Nykaa Pulse's own tables — np_feedback_items,
np_tickets, np_ticket_comments — deliberately kept separate from the shared
feedback_items/tickets/ticket_comments tables, so the two parts of this app
never mix data. Only `users` stays shared. See nykaa_store.py.
"""
import re
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field

from . import auth, classifier, feedback_ai, ticket_report
from . import nykaa_ai_features, nykaa_analytics, nykaa_insights, nykaa_store as npstore
from .models import Category, Team, TicketStatus

nykaa_router = APIRouter(prefix="/api/nykaa")

# Review photos only ("Show off your look!") — narrower than ticket
# attachments, which also allow PDFs/docs. Same 5MB ceiling as those.
ALLOWED_REVIEW_PHOTO_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_REVIEW_PHOTO_BYTES = 5 * 1024 * 1024

# Ticket-comment attachments — same allowed types/size ceiling as the shared
# tickets table's own attachments (main.py's ALLOWED_ATTACHMENT_TYPES),
# duplicated locally rather than imported to avoid a circular import
# (main.py imports this router to mount it).
ALLOWED_NP_ATTACHMENT_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "application/pdf", "text/plain", "text/csv",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
MAX_NP_ATTACHMENT_BYTES = 5 * 1024 * 1024


def _analyze_and_log(source_type: str, text: str, source_ref: int, user_id: int, rating: int | None = None):
    """Same shape as main.py's _analyze_and_log_feedback, duplicated locally
    (rather than imported) to avoid a circular import — main.py is the one
    that imports this router to mount it. Returns the analysis (unlike
    main.py's version) so callers can act on is_actionable_ticket — see
    submit_review's review-to-ticket auto-linking below. Logs into
    np_feedback_items — Nykaa Pulse's own copy, kept separate from the
    shared feedback_items table "My Existing Project" uses."""
    outcome = feedback_ai.analyze_feedback(text)
    a = outcome.analysis
    urgency_score = max(a.urgency_score, 0.5) if rating is not None and rating <= 2 else a.urgency_score
    npstore.save_np_feedback_item(
        source_type=source_type,
        source_ref=source_ref,
        user_id=user_id,
        rating=rating,
        text=text,
        sentiment_label=a.sentiment_label.value,
        sentiment_score=a.sentiment_score,
        category=a.category.value,
        theme=a.theme,
        urgency_score=urgency_score,
        is_actionable_ticket=a.is_actionable_ticket,
        model_used=outcome.model_used,
        mode=outcome.mode,
        latency_ms=outcome.latency_ms,
    )
    return a


# Deterministic hard-triggers — instant escalation for named severe cases,
# skipping the bot's "let me try to help" turn entirely for these (no
# customer with a clearly broken product should have to argue their way past
# a bot first). One group per team that can plausibly come up in a
# per-order-item chat — checked in this order, most severe first, so a
# message that touches more than one (e.g. "broken AND I want a refund")
# still lands on the more severe team. Only decides category/team, never
# priority — severity always comes from a real classifier.build_ticket_
# result() call (see chat_turn below), so a mildly-worded message about a
# minor issue doesn't automatically get treated as High just because it
# matched a keyword.
_HARD_TRIGGERS = [
    # Product Quality & Safety — something wrong with the product itself,
    # including the vaguer "quality issue" phrasing the model used to send
    # to Triage instead of recognizing outright. Counterfeit/authenticity
    # concerns are grouped here too — Product Quality Team's remit
    # explicitly covers counterfeit concerns, not just physical defects.
    (("broken", "damaged", "leak", "leaking", "shattered", "cracked", "spoiled", "expired", "spilled",
      "quality issue", "quality problem", "poor quality", "bad quality", "defective", "faulty",
      "product doesn't work", "product not working", "product stopped working",
      "allergic reaction", "allergic", "broke out in a rash", "skin rash", "skin irritation", "burning sensation",
      "tampered", "broken seal", "counterfeit", "fake product", "not genuine", "not authentic", "duplicate product"),
     Category.PRODUCT_QUALITY_SAFETY, Team.PRODUCT_QUALITY_TEAM),

    (("refund", "money back", "charged twice", "overcharged", "double charged",
      "payment failed", "payment declined", "not refunded", "unauthorized charge", "wrongly charged"),
     Category.PAYMENTS_REFUNDS, Team.PAYMENTS_BILLING_TEAM),

    (("replace", "replacement", "return this", "return it", "wrong item", "wrong product",
      "wrong shade", "wrong size", "exchange this", "send it back"),
     Category.RETURNS_REPLACEMENTS, Team.RETURNS_REFUNDS_TEAM),

    # No dedicated seller/vendor team anymore — Triage is the normal
    # destination for this category (see models.Team and classifier.py's
    # routing table for the full category -> team mapping).
    (("seller not responding", "seller is not responding", "seller isn't responding"),
     Category.SELLER_VENDOR_ISSUE, Team.TRIAGE),

    (("app crashing", "app crashes", "app keeps crashing", "app not working", "website not working",
      "site is down", "checkout failed", "checkout error", "page won't load"),
     Category.APP_WEBSITE_ISSUE, Team.TECHNICAL_SUPPORT_TEAM),

    (("can't log in", "cannot log in", "locked out of my account", "forgot my password",
      "otp not received", "account hacked", "account compromised"),
     Category.ACCOUNT_ACCESS, Team.ACCOUNT_LOYALTY_TEAM),
]


def _hard_trigger_category_team(message: str) -> tuple[Category, Team] | None:
    text = message.lower()
    for keywords, category, team in _HARD_TRIGGERS:
        if any(k in text for k in keywords):
            return category, team
    return None


# Deterministic, zero-LLM-call guardrail for pure small talk / general-
# knowledge asks that have nothing to do with an order or product (arithmetic,
# "what's the time", greetings, thanks) — these used to fall through to
# run_chat_turn and then, on the very next message, get force-escalated to a
# real team purely because MAX_BOT_TURNS counted every customer turn
# regardless of topic. Answered directly and instantly here instead: never
# escalated, and excluded from the MAX_BOT_TURNS count (see chat_turn) so chit
# -chat can't burn through the turn budget meant for a genuine issue.
_GREETING_RE = re.compile(r"^(hi+|hello+|hey+|yo|sup|good\s*(morning|afternoon|evening))[\s!.,?]*$", re.IGNORECASE)
_THANKS_RE = re.compile(r"^(thanks?( you)?|thx|ty|ok(ay)?|cool|great|got it|nice one)[\s!.,?]*$", re.IGNORECASE)
_HOW_ARE_YOU_RE = re.compile(r"\bhow('?s| is| are)\s+(you|it going|things)\b", re.IGNORECASE)
_TIME_DATE_RE = re.compile(
    r"\bwhat('?s| is)\b[^?]*\b(time|date|day)\b|\bwhat\s+(time|day)\s+is\s+it\b", re.IGNORECASE
)
_ARITHMETIC_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*([+\-*/])\s*(-?\d+(?:\.\d+)?)\s*$")


def _arithmetic_answer(text: str) -> str | None:
    match = _ARITHMETIC_RE.match(text)
    if not match:
        return None
    a, op, b = float(match.group(1)), match.group(2), float(match.group(3))
    if op == "+":
        result = a + b
    elif op == "-":
        result = a - b
    elif op == "*":
        result = a * b
    elif b == 0:
        return None
    else:
        result = a / b
    result = int(result) if result == int(result) else round(result, 4)
    return f"That's {result}. Is there something about your order I can help with?"


def _general_chitchat_reply(message: str) -> str | None:
    """Returns a direct reply for pure chit-chat/general-knowledge messages,
    or None if this looks like it could be a real order/product issue (in
    which case the normal hard-trigger/LLM/escalation flow handles it)."""
    text = message.strip()
    arithmetic = _arithmetic_answer(text)
    if arithmetic is not None:
        return arithmetic
    if _TIME_DATE_RE.search(text):
        now = datetime.now(timezone.utc)
        return f"Right now it's {now.strftime('%H:%M UTC')} on {now.strftime('%B %d, %Y')}. Is there something about your order I can help with?"
    if _GREETING_RE.match(text) or _HOW_ARE_YOU_RE.search(text):
        return "Hey there! How can I help with your order today?"
    if _THANKS_RE.match(text):
        return "You're welcome! Let me know if anything else comes up with your order."
    return None


def _backfill_ticket_summary(ticket_id: int, message: str) -> None:
    npstore.update_np_ticket_summary(ticket_id, nykaa_ai_features.summarize_ticket_issue(message))


def _finalize_np_ticket(
    order_id: int, item: dict, user_id: int, message: str, classification: dict,
    background_tasks: BackgroundTasks | None = None,
) -> dict:
    """Core of ticket creation: idempotency guard + persist + link + mirror
    into the feedback log. `classification` is a classifier.build_ticket_
    result()-shaped dict — either computed fresh (hard-trigger / manual
    raise) or already produced by nykaa_ai_features.run_chat_turn's own
    escalate decision, so escalating from the chat never costs a second
    classification call.

    `background_tasks`, when given (chat_turn's escalation path — a customer
    is actively waiting on this response), skips both non-essential LLM calls
    from the request itself: the ticket is created immediately with the same
    instant fallback title summarize_ticket_issue would've used anyway if no
    provider were configured, and both the nicer AI-written title and the
    PM-analytics feedback-log entry (_analyze_and_log — its own LLM call,
    never used by the reply itself) are done right after the response goes
    out instead of before. Without a customer waiting synchronously (manual
    raise / review auto-linking), both run up front as before — there's no
    latency to hide them from, and review auto-linking needs analyze_feedback's
    own result immediately to decide whether to open a ticket at all."""
    if item.get("linked_ticket_id"):
        existing = npstore.get_np_ticket(item["linked_ticket_id"])
        if existing:
            return existing
    if background_tasks is not None:
        summary = nykaa_ai_features.fallback_ticket_title(message)
    else:
        summary = nykaa_ai_features.summarize_ticket_issue(message)
    ticket = npstore.create_np_ticket(order_id, item["id"], user_id, message, classification, summary)
    npstore.set_linked_ticket(item["id"], ticket["id"])
    if background_tasks is not None:
        background_tasks.add_task(_backfill_ticket_summary, ticket["id"], message)
        background_tasks.add_task(_analyze_and_log, "ticket", message, ticket["id"], user_id)
    else:
        _analyze_and_log("ticket", message, ticket["id"], user_id)
    return ticket


def _create_and_tag_ticket(order_id: int, item: dict, user_id: int, message: str) -> dict:
    """Idempotent: an order item can only ever be linked to one ticket. If
    it already has one (raised manually earlier, or auto-opened by a prior
    actionable review), returns that ticket instead of opening a second one.

    Convenience wrapper for callers that don't already have a classification
    in hand (review auto-linking, manual raise) — classifies fresh via
    classifier.py, then delegates to _finalize_np_ticket. Nykaa Pulse tickets
    live in their own np_tickets table, separate from the shared tickets
    table "My Existing Project" uses — see nykaa_store.py."""
    if item.get("linked_ticket_id"):
        existing = npstore.get_np_ticket(item["linked_ticket_id"])
        if existing:
            return existing
    classification = classifier.build_ticket_result(message, manual_time_seconds=None, compare=False)
    return _finalize_np_ticket(order_id, item, user_id, message, classification)


# ---- request bodies ---------------------------------------------------------

class OrderLineItem(BaseModel):
    product_id: int
    quantity: int = Field(ge=1, default=1)


class PlaceOrderRequest(BaseModel):
    items: list[OrderLineItem] = Field(min_length=1)


class ReviewSubmitRequest(BaseModel):
    """rating/title/description are each independently optional — the
    review form never forces all three together (see nykaa_store.py)."""
    rating: int | None = Field(default=None, ge=1, le=5)
    title: str | None = None
    description: str | None = None


class ReviewTitleRequest(BaseModel):
    description: str = Field(min_length=1, max_length=1000)


class DeliveryRatingRequest(BaseModel):
    rating: int = Field(ge=1, le=5)
    compliment: str | None = None


class AppFeedbackRequest(BaseModel):
    rating: int = Field(ge=1, le=5)
    categories: list[str] = Field(min_length=1, max_length=6)
    description: str | None = Field(default=None, max_length=1000)


class ChatTurnRequest(BaseModel):
    message: str = Field(min_length=1)


class NpTicketCommentRequest(BaseModel):
    body: str = Field(min_length=1)


class NpTicketStatusUpdateRequest(BaseModel):
    status: TicketStatus


class NpTicketCsatRequest(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = None


class AskReviewsRequest(BaseModel):
    question: str = Field(min_length=1, max_length=300)


class BeautyProfileRequest(BaseModel):
    """Every field is independently optional — same "no forced format"
    principle as ReviewSubmitRequest. Free-text rather than closed enums so
    the frontend can offer a curated dropdown without the backend needing to
    know every possible value."""
    skin_type: str | None = None
    skin_concerns: list[str] | None = None
    date_of_birth: str | None = None
    hair_type: str | None = None
    scalp_type: str | None = None
    hair_concerns: list[str] | None = None
    skin_tone: str | None = None
    undertone: str | None = None
    makeup_preferences: str | None = None


# ---- catalog (any logged-in role can browse) --------------------------------

@nykaa_router.get("/catalog/categories")
def list_categories():
    return {"categories": npstore.list_categories()}


@nykaa_router.get("/catalog/brands")
def list_brands(category_id: int | None = None):
    return {"brands": npstore.list_brands(category_id)}


@nykaa_router.get("/catalog/subcategories")
def list_subcategories(category_id: int | None = None):
    return {"subcategories": npstore.list_subcategories(category_id)}


@nykaa_router.get("/catalog/products")
def list_products(category_id: int | None = None, brand_id: int | None = None,
                   subcategory_id: int | None = None, search: str | None = None):
    return {"products": npstore.list_products(category_id, brand_id, subcategory_id, search)}


@nykaa_router.get("/catalog/products/{product_id}")
def get_product(product_id: int):
    product = npstore.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="product not found")
    return product


@nykaa_router.get("/catalog/products/{product_id}/summary")
def get_product_summary(product_id: int, claims: dict = Depends(auth.require_any)):
    """Fit summarizer — cross-references each reviewer's current Beauty
    Portfolio skin type against their rating (see
    nykaa_ai_features._skin_type_segments) so this can genuinely answer
    "will this suit someone like me," not just "do people like this"."""
    product = npstore.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="product not found")
    reviews = npstore.list_published_reviews_with_profile(product_id)
    return nykaa_ai_features.summarize_product_reviews(product, reviews)


@nykaa_router.get("/catalog/products/{product_id}/reviews")
def get_product_reviews(product_id: int, claims: dict = Depends(auth.require_any)):
    """Published reviews for one product, each tagged with the reviewer's
    current Beauty Portfolio attributes (nullable) — the "someone with my
    skin type liked this" attribution the teardown research called out as
    Nykaa's clearest differentiator."""
    return {"reviews": npstore.list_published_reviews_with_profile(product_id)}


@nykaa_router.post("/catalog/products/{product_id}/ask")
def ask_reviews(product_id: int, req: AskReviewsRequest, claims: dict = Depends(auth.require_any)):
    """Phase 4 "ask the reviews" — grounded Q&A over one product's published
    review corpus, stuffed directly into context (no vector search — the
    review counts here don't warrant one)."""
    product = npstore.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="product not found")
    review_texts = npstore.list_published_review_texts(product_id)
    return nykaa_ai_features.answer_review_question(product["name"], review_texts, req.question)


# ---- customer: Beauty Portfolio ---------------------------------------------

@nykaa_router.get("/beauty-profile")
def get_beauty_profile(claims: dict = Depends(auth.require_user)):
    profile = npstore.get_beauty_profile(int(claims["sub"]))
    return profile or {
        "user_id": int(claims["sub"]), "skin_type": None, "skin_concerns": [], "date_of_birth": None,
        "hair_type": None, "scalp_type": None, "hair_concerns": [], "skin_tone": None, "undertone": None,
        "makeup_preferences": None,
    }


@nykaa_router.put("/beauty-profile")
def put_beauty_profile(req: BeautyProfileRequest, claims: dict = Depends(auth.require_user)):
    return npstore.upsert_beauty_profile(
        int(claims["sub"]), req.skin_type, req.hair_type, req.makeup_preferences,
        req.skin_concerns, req.date_of_birth, req.scalp_type, req.hair_concerns, req.skin_tone, req.undertone,
    )


@nykaa_router.get("/catalog/recommended")
def catalog_recommended(section: str = "skin", claims: dict = Depends(auth.require_user)):
    """Powers the Beauty Profile page's "Recommended for you" tabs (Skin/
    Hair/Makeup) — matches the customer's own saved profile for that one
    section, falling back to that section's top-rated products when
    nothing matches yet."""
    if section not in ("skin", "hair", "makeup"):
        raise HTTPException(status_code=400, detail="section must be one of: skin, hair, makeup")
    profile = npstore.get_beauty_profile(int(claims["sub"])) or {}
    return {"products": npstore.list_recommended_products(section, profile)}


@nykaa_router.get("/beauty-profile/routine")
def beauty_profile_routine(claims: dict = Depends(auth.require_user)):
    """"Generate My Routine" — every canonical step (Cleanser, Serum,
    Moisturizer, Sunscreen for skincare; Shampoo, Conditioner, Hair Oil,
    Styling for haircare) is always populated with a real product matched
    to this profile's type/concerns, not gated on that product having any
    reviews yet (see npstore.compute_routine_candidates)."""
    profile = npstore.get_beauty_profile(int(claims["sub"])) or {}
    return nykaa_ai_features.generate_beauty_routine(profile, npstore.compute_routine_candidates(profile))


# ---- customer: orders, reviews, delivery rating, raise-ticket --------------

@nykaa_router.post("/orders")
def place_order(req: PlaceOrderRequest, claims: dict = Depends(auth.require_user)):
    order = npstore.create_order(int(claims["sub"]), [item.model_dump() for item in req.items])
    return order


@nykaa_router.get("/orders/mine")
def my_orders(claims: dict = Depends(auth.require_user)):
    return {"orders": npstore.list_orders_for_user(int(claims["sub"]))}


def _get_own_order_or_404(order_id: int, user_id: int) -> dict:
    order = npstore.get_order(order_id)
    if not order or order["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="order not found")
    return order


@nykaa_router.post("/orders/{order_id}/items/{item_id}/review")
def submit_review(order_id: int, item_id: int, req: ReviewSubmitRequest, claims: dict = Depends(auth.require_user)):
    user_id = int(claims["sub"])
    order = _get_own_order_or_404(order_id, user_id)
    item = next((i for i in order["items"] if i["id"] == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="order item not found")

    # Real Nykaa forces both title and description — this app doesn't:
    # description is the primary field, and when the customer leaves the
    # title blank but did write a description, one is generated from it.
    title = req.title.strip() if req.title and req.title.strip() else None
    if title is None and req.description and req.description.strip():
        title = nykaa_ai_features.summarize_review_title(req.description.strip())
    updated = npstore.submit_item_review(order_id, item_id, req.rating, title, req.description)

    # Analyze whatever text the customer actually gave — title + description
    # if present, otherwise a plain sentence describing the star rating alone,
    # so a rating-only submission still produces a real sentiment/category
    # read instead of being skipped.
    text_parts = [p for p in (title, req.description) if p and p.strip()]
    text = " — ".join(text_parts) if text_parts else f"Rated {item['product_name']} {req.rating} out of 5 stars, no written review."
    analysis = _analyze_and_log("review", text, item_id, user_id, req.rating)

    # Review-to-ticket auto-linking: a review the AI judges genuinely
    # actionable (e.g. "arrived broken", "leaking") opens a support ticket
    # on its own — closing the loop instead of requiring the customer to
    # separately click "Raise a Ticket" for the same problem they just
    # described. _create_and_tag_ticket's linked_ticket_id guard means this
    # never creates a second ticket if one already exists for this item.
    auto_ticket_id = None
    if analysis.is_actionable_ticket and not item.get("linked_ticket_id"):
        ticket_message = f"Auto-flagged from a review on order #{order_id} — {item['product_name']}: {text}"
        auto_ticket_id = _create_and_tag_ticket(order_id, {**item, "linked_ticket_id": None}, user_id, ticket_message)["id"]

    result = dict(updated)
    result["auto_ticket_id"] = auto_ticket_id
    return result


@nykaa_router.post("/reviews/generate-title")
def generate_review_title(req: ReviewTitleRequest, claims: dict = Depends(auth.require_user)):
    """Backs the "Rate & Review" modal's own "Generate" button — lets a
    customer preview (and edit) the AI-written title before submitting,
    rather than only ever seeing it applied silently at submit time (see
    submit_review's same summarize_review_title call above for the blank-
    title fallback path)."""
    return {"title": nykaa_ai_features.summarize_review_title(req.description.strip())}


@nykaa_router.post("/orders/{order_id}/delivery-rating")
def submit_delivery_rating(order_id: int, req: DeliveryRatingRequest, claims: dict = Depends(auth.require_user)):
    order = _get_own_order_or_404(order_id, int(claims["sub"]))
    return npstore.submit_delivery_rating(order["id"], req.rating, req.compliment)


@nykaa_router.post("/app-feedback")
def submit_app_feedback(req: AppFeedbackRequest, claims: dict | None = Depends(auth.require_user_optional)):
    """Rating + what went wrong about the shop app itself — not a product
    review, not a support ticket. Also reachable from the login page for a
    visitor who isn't signed in yet (e.g. reporting trouble logging in
    itself), so auth is optional here — user_id stays NULL for those, same
    as any other unattributed row. No AI involved at all: the categories are
    already fixed, customer-picked labels, and this feedback type has no
    title field (see FeedbackModal's product review for that instead)."""
    user_id = int(claims["sub"]) if claims else None
    return npstore.save_app_feedback(user_id, req.rating, req.categories, req.description)


def _transcript(turns: list[dict]) -> str:
    return "\n".join(f'{"Customer" if t["role"] == "user" else "Assistant"}: {t["text"]}' for t in turns)


# Hard-triggered messages (see _HARD_TRIGGERS above) escalate on turn one,
# regardless of this cap — this only bounds how long the bot keeps trying to
# help with something that matched no known-severe keyword before handing
# off anyway, so a genuinely unclear issue doesn't drag on for several
# back-and-forth replies before a human gets involved.
MAX_BOT_TURNS = 2


@nykaa_router.get("/orders/{order_id}/items/{item_id}/chat")
def chat_history(order_id: int, item_id: int, claims: dict = Depends(auth.require_user)):
    """Prior bot-phase turns (np_chat_turns) for this item — lets the
    floating chatbot/"Help" modal restore an in-progress (not yet escalated)
    conversation when reopened, instead of restarting from the greeting
    every time."""
    user_id = int(claims["sub"])
    order = _get_own_order_or_404(order_id, user_id)
    if not any(i["id"] == item_id for i in order["items"]):
        raise HTTPException(status_code=404, detail="order item not found")
    return {"turns": npstore.list_chat_turns(order_id, item_id)}


@nykaa_router.post("/orders/{order_id}/items/{item_id}/chat")
def chat_turn(
    order_id: int, item_id: int, req: ChatTurnRequest, background_tasks: BackgroundTasks,
    claims: dict = Depends(auth.require_user),
):
    """One turn of "Raise a Ticket"'s multi-turn support chat. Persists the
    customer's message, then either (a) hard-triggers an instant escalation
    on a known-severe keyword, (b) forces escalation once MAX_BOT_TURNS is
    reached, (c) lets nykaa_ai_features.run_chat_turn decide, or (d) keeps
    chatting. On escalation, the prior bot-phase transcript (np_chat_turns)
    is copied into np_ticket_comments so the human agent who eventually
    opens the ticket sees full context, not a blank thread, capped off with
    a handoff system message."""
    user_id = int(claims["sub"])
    order = _get_own_order_or_404(order_id, user_id)
    item = next((i for i in order["items"] if i["id"] == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="order item not found")

    # Already escalated — this item's chat is done; the customer should be
    # using the ticket's own comment thread from here on.
    if item.get("linked_ticket_id"):
        ticket = npstore.get_np_ticket(item["linked_ticket_id"])
        if ticket:
            return {"reply": None, "escalated": True, "ticket": ticket}

    message = req.message.strip()
    # _with_attachments (not the JSON-safe list_chat_turns) because the
    # escalation branch below needs any attachment bytes from earlier bot-
    # phase turns to carry them into the ticket thread — this return value is
    # never serialized back to the client, so it's safe to include raw bytes.
    prior_turns = npstore.list_chat_turns_with_attachments(order_id, item_id)

    chitchat_reply = _general_chitchat_reply(message)
    if chitchat_reply is not None:
        npstore.add_chat_turn(order_id, item_id, "user", message)
        npstore.add_chat_turn(order_id, item_id, "bot", chitchat_reply)
        return {"reply": chitchat_reply, "escalated": False}

    npstore.add_chat_turn(order_id, item_id, "user", message)

    # Only real (non-chit-chat) turns count toward the forced-escalation cap
    # — otherwise a customer testing the bot with off-topic messages burns
    # through the turn budget meant for genuine issues and gets force-
    # escalated to a human team for no reason.
    customer_turns_so_far = len(
        [t for t in prior_turns if t["role"] == "user" and _general_chitchat_reply(t["text"]) is None]
    ) + 1
    forced = customer_turns_so_far >= MAX_BOT_TURNS
    hard_trigger = _hard_trigger_category_team(message)

    if hard_trigger is None and not forced:
        history = [{"role": t["role"], "text": t["text"]} for t in prior_turns]
        context = (
            f"Order #{order_id}, product \"{item['product_name']}\", quantity {item['quantity']}, "
            f"₹{item['unit_price_at_purchase']} each, order status \"{order['status']}\"."
        )
        outcome = nykaa_ai_features.run_chat_turn(history, message, context)
        if not outcome["escalate"]:
            npstore.add_chat_turn(order_id, item_id, "bot", outcome["reply"])
            return {"reply": outcome["reply"], "escalated": False}
        # run_chat_turn's own escalate path already asked the model for a
        # genuine priority/tone/confidence — no static value involved. Its
        # own reply is a natural handoff message, not a generic template.
        classification = outcome
        reply_text = outcome["reply"]
    else:
        # Hard-triggered or forced by the turn cap — either way, escalating.
        # Priority/tone/confidence/reasoning always come from a real
        # classification of the full transcript, never a fixed value; when
        # hard-triggered, only category/team are overlaid from the keyword
        # match (those two are reliable from wording alone — severity isn't).
        classification = classifier.build_ticket_result(
            _transcript(prior_turns + [{"role": "user", "text": message}]), manual_time_seconds=None, compare=False
        )
        if hard_trigger is not None:
            category, team = hard_trigger
            classification = {**classification, "category": category.value, "team": team.value}
        reply_text = f"I've connected you with our {classification['team']} — they'll take it from here."

    npstore.add_chat_turn(order_id, item_id, "bot", reply_text)
    # Built from what we already have in memory rather than re-fetching from
    # np_chat_turns — this exact sequence (prior_turns, then the message and
    # reply just inserted above) is what that query would return anyway, and
    # a round trip to a cross-region Postgres instance is expensive enough
    # here that skipping an avoidable one is worth it.
    full_transcript_turns = prior_turns + [{"role": "user", "text": message}, {"role": "bot", "text": reply_text}]
    full_transcript = _transcript(full_transcript_turns)
    ticket = _finalize_np_ticket(order_id, item, user_id, full_transcript, classification, background_tasks)

    # Bulk-copy the bot-phase transcript into the ticket's own thread so the
    # human agent opens it already seeing full context, then cap it with a
    # handoff message — everything from here on happens in that thread. One
    # multi-row insert instead of one round trip per line — the same reason
    # as above, just bigger (this loop used to be the single largest
    # contributor to how slow escalating a chat felt).
    npstore.add_np_ticket_comments_bulk(
        ticket["id"],
        [
            {
                "author_role": "user" if t["role"] == "user" else "bot",
                "author_name": claims["name"] if t["role"] == "user" else "NykaaPulse Assistant",
                "text": t["text"],
                "attachment_data": t.get("attachment_data"),
                "attachment_name": t.get("attachment_name"),
                "attachment_mime": t.get("attachment_mime"),
            }
            for t in full_transcript_turns
        ]
        + [{"author_role": "bot", "author_name": "NykaaPulse Assistant", "text": f"You've been connected to our {ticket['team']} — they'll follow up here shortly."}],
    )

    return {"reply": reply_text, "escalated": True, "ticket": ticket}


@nykaa_router.post("/orders/{order_id}/items/{item_id}/chat/attachments")
async def upload_chat_attachment(order_id: int, item_id: int, file: UploadFile = File(...), claims: dict = Depends(auth.require_user)):
    """A file attached during the bot phase, before any ticket exists yet —
    stored as a np_chat_turns row with no text, same allowed-types/size
    ceiling as a post-escalation ticket attachment. If this chat later
    escalates, chat_turn's own bulk-copy carries it into the ticket thread
    automatically (see list_chat_turns_with_attachments)."""
    user_id = int(claims["sub"])
    order = _get_own_order_or_404(order_id, user_id)
    item = next((i for i in order["items"] if i["id"] == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="order item not found")
    if item.get("linked_ticket_id"):
        raise HTTPException(status_code=400, detail="this chat has already been escalated — attach files to the ticket thread instead")
    if file.content_type not in ALLOWED_NP_ATTACHMENT_TYPES:
        raise HTTPException(status_code=400, detail=f"unsupported file type: {file.content_type}")

    contents = await file.read()
    if len(contents) > MAX_NP_ATTACHMENT_BYTES:
        raise HTTPException(status_code=400, detail="file too large (max 5MB)")

    return npstore.add_chat_turn(
        order_id, item_id, "user", "",
        attachment_data=contents, attachment_name=file.filename or "attachment", attachment_mime=file.content_type,
    )


@nykaa_router.get("/orders/{order_id}/items/{item_id}/chat/attachments/{turn_id}")
def download_chat_attachment(order_id: int, item_id: int, turn_id: int, claims: dict = Depends(auth.require_user)):
    order = _get_own_order_or_404(order_id, int(claims["sub"]))
    if not any(i["id"] == item_id for i in order["items"]):
        raise HTTPException(status_code=404, detail="order item not found")
    turn = npstore.get_chat_turn(turn_id)
    if not turn or turn["order_id"] != order_id or turn["item_id"] != item_id or not turn["attachment_data"]:
        raise HTTPException(status_code=404, detail="attachment not found")
    safe_name = (turn["attachment_name"] or "attachment").replace('"', "").replace("\n", "").replace("\r", "")
    return Response(
        content=turn["attachment_data"],
        media_type=turn["attachment_mime"] or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


@nykaa_router.post("/orders/{order_id}/items/{item_id}/review/photo")
async def upload_review_photo(order_id: int, item_id: int, file: UploadFile = File(...), claims: dict = Depends(auth.require_user)):
    """"Show off your look!" — a photo attached to a review, always optional."""
    user_id = int(claims["sub"])
    order = _get_own_order_or_404(order_id, user_id)
    if not any(i["id"] == item_id for i in order["items"]):
        raise HTTPException(status_code=404, detail="order item not found")
    if file.content_type not in ALLOWED_REVIEW_PHOTO_TYPES:
        raise HTTPException(status_code=400, detail=f"unsupported file type: {file.content_type}")

    contents = await file.read()
    if len(contents) > MAX_REVIEW_PHOTO_BYTES:
        raise HTTPException(status_code=400, detail="file too large (max 5MB)")

    npstore.save_review_photo(order_id, item_id, contents, file.filename or "photo", file.content_type)
    return {"ok": True}


@nykaa_router.get("/orders/{order_id}/items/{item_id}/review/photo")
def get_review_photo(order_id: int, item_id: int, claims: dict = Depends(auth.require_any)):
    photo = npstore.get_review_photo(item_id)
    if not photo or photo["order_id"] != order_id:
        raise HTTPException(status_code=404, detail="photo not found")
    if claims["role"] == "user":
        _get_own_order_or_404(order_id, int(claims["sub"]))  # raises 404 if this isn't their order

    safe_name = (photo["name"] or "photo").replace('"', "").replace("\n", "").replace("\r", "")
    return Response(
        content=photo["data"],
        media_type=photo["mime"] or "application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="{safe_name}"'},
    )


# ---- np_ticket comment threads (customer + team, post-escalation) ----------
# Same access-control/messaging-open shape as main.py's generic ticket
# comment endpoints, scoped to np_tickets instead of the shared tickets
# table. "user" here is the ticket's own customer (Nykaa Pulse tickets have
# no separate "team-assigned observer" admin role wired up yet).

def _can_access_np_ticket_comments(ticket: dict, claims: dict) -> bool:
    role = claims["role"]
    if role == "admin":
        return True
    if role == "user":
        return ticket["user_id"] == int(claims["sub"])
    if role == "team":
        return ticket.get("team") == claims.get("team")
    return False


def _np_ticket_messaging_open(ticket: dict) -> bool:
    return ticket["status"] == "In Progress"


def _np_viewer_key(claims: dict) -> str | None:
    if claims["role"] == "user":
        return str(claims["sub"])
    if claims["role"] == "team":
        return claims["team"]
    return None


@nykaa_router.get("/tickets/{ticket_id}/comments")
def get_np_ticket_comments(ticket_id: int, claims: dict = Depends(auth.require_any)):
    ticket = npstore.get_np_ticket(ticket_id)
    if not ticket or not _can_access_np_ticket_comments(ticket, claims):
        raise HTTPException(status_code=404, detail="ticket not found")
    return {
        "comments": npstore.list_np_ticket_comments(ticket_id),
        "messaging_open": _np_ticket_messaging_open(ticket),
        "status": ticket["status"],
        "csat_rating": ticket.get("csat_rating"),
    }


@nykaa_router.post("/tickets/{ticket_id}/comments/read")
def mark_np_ticket_comments_read(ticket_id: int, claims: dict = Depends(auth.require_any)):
    ticket = npstore.get_np_ticket(ticket_id)
    if not ticket or not _can_access_np_ticket_comments(ticket, claims):
        raise HTTPException(status_code=404, detail="ticket not found")
    viewer_key = _np_viewer_key(claims)
    if viewer_key is not None:
        npstore.mark_np_comments_read(ticket_id, claims["role"], viewer_key)
    return {"marked_read": True}


@nykaa_router.post("/tickets/{ticket_id}/comments")
def post_np_ticket_comment(ticket_id: int, req: NpTicketCommentRequest, claims: dict = Depends(auth.require_any)):
    ticket = npstore.get_np_ticket(ticket_id)
    if not ticket or not _can_access_np_ticket_comments(ticket, claims):
        raise HTTPException(status_code=404, detail="ticket not found")
    if not _np_ticket_messaging_open(ticket):
        raise HTTPException(status_code=400, detail="messaging is only available while a ticket is in progress")
    return npstore.add_np_ticket_comment(ticket_id, claims["role"], claims["name"], req.body)


@nykaa_router.post("/tickets/{ticket_id}/attachments")
async def post_np_ticket_attachment(ticket_id: int, file: UploadFile = File(...), claims: dict = Depends(auth.require_any)):
    """A document/file attached to a ticket's chat instead of (or with) a
    text reply — customer or team side, same gate as a plain comment. The
    human agent on the other end can open (and the PDF report can embed)
    whatever gets attached here."""
    ticket = npstore.get_np_ticket(ticket_id)
    if not ticket or not _can_access_np_ticket_comments(ticket, claims):
        raise HTTPException(status_code=404, detail="ticket not found")
    if not _np_ticket_messaging_open(ticket):
        raise HTTPException(status_code=400, detail="messaging is only available while a ticket is in progress")
    if file.content_type not in ALLOWED_NP_ATTACHMENT_TYPES:
        raise HTTPException(status_code=400, detail=f"unsupported file type: {file.content_type}")

    contents = await file.read()
    if len(contents) > MAX_NP_ATTACHMENT_BYTES:
        raise HTTPException(status_code=400, detail="file too large (max 5MB)")

    return npstore.add_np_ticket_comment(
        ticket_id, claims["role"], claims["name"], body="",
        attachment_data=contents, attachment_name=file.filename or "attachment", attachment_mime=file.content_type,
    )


@nykaa_router.get("/tickets/{ticket_id}/attachments/{comment_id}")
def get_np_ticket_attachment(ticket_id: int, comment_id: int, claims: dict = Depends(auth.require_any)):
    ticket = npstore.get_np_ticket(ticket_id)
    if not ticket or not _can_access_np_ticket_comments(ticket, claims):
        raise HTTPException(status_code=404, detail="ticket not found")
    comment = npstore.get_np_ticket_comment(comment_id)
    if not comment or comment["np_ticket_id"] != ticket_id or not comment["attachment_data"]:
        raise HTTPException(status_code=404, detail="attachment not found")
    safe_name = (comment["attachment_name"] or "attachment").replace('"', "").replace("\n", "").replace("\r", "")
    return Response(
        content=comment["attachment_data"],
        media_type=comment["attachment_mime"] or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


@nykaa_router.post("/tickets/{ticket_id}/csat")
def submit_np_ticket_csat(ticket_id: int, req: NpTicketCsatRequest, claims: dict = Depends(auth.require_user)):
    """5-star "how was your support experience" rating — only once the
    ticket is Resolved, and only once (no overwriting an earlier rating)."""
    ticket = npstore.get_np_ticket(ticket_id)
    if not ticket or ticket["user_id"] != int(claims["sub"]):
        raise HTTPException(status_code=404, detail="ticket not found")
    if ticket["status"] != "Resolved":
        raise HTTPException(status_code=400, detail="this ticket isn't resolved yet")
    if ticket.get("csat_rating") is not None:
        raise HTTPException(status_code=400, detail="this ticket has already been rated")
    return npstore.submit_np_ticket_csat(ticket_id, req.rating, req.comment)


# ---- admin: order oversight -------------------------------------------------

@nykaa_router.get("/admin/orders")
def admin_list_orders(claims: dict = Depends(auth.require_admin)):
    return {"orders": npstore.list_all_orders()}


@nykaa_router.get("/admin/tickets")
def admin_list_np_tickets(claims: dict = Depends(auth.require_admin)):
    """Nykaa Pulse's own ticket oversight for Admin — mirrors what Admin
    already sees for the shared tickets table (AllTicketsPage.jsx), just
    sourced from np_tickets across every team."""
    return {"tickets": npstore.list_all_np_tickets()}


@nykaa_router.get("/admin/analytics")
def admin_np_analytics(claims: dict = Depends(auth.require_admin)):
    return nykaa_analytics.compute_ticket_analytics()


@nykaa_router.get("/admin/tickets/{ticket_id}/report.pdf")
def admin_np_ticket_report(ticket_id: int, claims: dict = Depends(auth.require_admin)):
    ticket = npstore.get_np_ticket_with_user(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="ticket not found")
    comments = npstore.list_np_ticket_comments_with_attachments(ticket_id)
    pdf_bytes = ticket_report.generate_ticket_report(ticket, comments)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="nykaa-ticket-{ticket_id}-report.pdf"'},
    )


# ---- resolved by AI, no ticket raised (admin + team, team-agnostic) --------

def _require_admin_or_team(claims: dict = Depends(auth.require_any)) -> dict:
    if claims["role"] not in ("admin", "team"):
        raise HTTPException(status_code=403, detail="admin or team role required")
    return claims


@nykaa_router.get("/ai-resolved-chats")
def ai_resolved_chats(claims: dict = Depends(_require_admin_or_team)):
    """Every Nykaa Pulse conversation the bot handled without ever
    escalating — never routed to a team, so this is unfiltered for both
    Admin and Team (transparency into what the bot is already handling)."""
    return {"chats": npstore.list_ai_resolved_chats()}


@nykaa_router.get("/ai-resolved-chats/{order_id}/{item_id}")
def ai_resolved_chat_transcript(order_id: int, item_id: int, claims: dict = Depends(_require_admin_or_team)):
    return {"turns": npstore.list_chat_turns(order_id, item_id)}


# ---- team: Nykaa Pulse's own tickets ----------------------------------------

@nykaa_router.get("/team/order-tickets")
def team_order_tickets(claims: dict = Depends(auth.require_team)):
    """This team's queue of Nykaa Pulse tickets — np_tickets, entirely
    separate from the shared tickets table "My Existing Project" uses.
    Already joined with product/brand name for context (see
    nykaa_store.list_np_tickets_for_team)."""
    tickets = npstore.list_np_tickets_for_team(claims["team"])
    unread = npstore.unread_np_comment_counts([t["id"] for t in tickets], "team", claims["team"])
    for t in tickets:
        t["unread_comments"] = unread.get(t["id"], 0)
    return {"tickets": tickets}


# Status only ever moves forward — same rule the shared tickets table's
# team queue already enforces (main.py's _ALLOWED_STATUS_MOVES).
_ALLOWED_NP_STATUS_MOVES = {
    "Routed": {"Routed", "In Progress", "Resolved"},
    "In Progress": {"In Progress", "Resolved"},
    "Resolved": {"Resolved"},
}


@nykaa_router.patch("/team/order-tickets/{ticket_id}/status")
def team_update_np_ticket_status(ticket_id: int, req: NpTicketStatusUpdateRequest, claims: dict = Depends(auth.require_team)):
    ticket = npstore.get_np_ticket(ticket_id)
    if not ticket or ticket.get("team") != claims["team"]:
        raise HTTPException(status_code=404, detail="ticket not found")
    allowed = _ALLOWED_NP_STATUS_MOVES.get(ticket["status"], set())
    if req.status.value not in allowed:
        raise HTTPException(status_code=400, detail=f"a {ticket['status']} ticket can't be moved back to {req.status.value}")
    return npstore.update_np_ticket_status(ticket_id, req.status.value)


# ---- PM: catalog-aware analytics (Phase 3) ---------------------------------

@nykaa_router.get("/pm/overview")
def pm_overview(claims: dict = Depends(auth.require_pm)):
    return nykaa_insights.overview()


@nykaa_router.get("/pm/feedback")
def pm_feedback(claims: dict = Depends(auth.require_pm)):
    """Every Nykaa Pulse review, in full — the PM's raw "All Feedback" list,
    mirroring the Mission side's /api/pm/feedback (store.list_feedback_items),
    just catalog-joined (brand/category/product) instead of ticket-shaped."""
    return {"items": npstore.list_review_feedback_with_catalog()}


@nykaa_router.get("/pm/product-rollup")
def pm_product_rollup(claims: dict = Depends(auth.require_pm)):
    return {"products": npstore.compute_product_rollup()}


@nykaa_router.get("/pm/app-feedback")
def pm_app_feedback(claims: dict = Depends(auth.require_pm)):
    """The technical/app-experience feedback customers leave via the
    shop's floating widget — a separate stream from product reviews,
    since it isn't about any brand/category/product."""
    return {"items": npstore.list_app_feedback()}


@nykaa_router.get("/pm/app-feedback/analytics")
def pm_app_feedback_analytics(claims: dict = Depends(auth.require_pm)):
    """Aggregate-only view (rating distribution + category counts) for the
    App Feedback tab — no raw feedback text, just the numbers."""
    return npstore.compute_app_feedback_breakdown()


@nykaa_router.get("/pm/delivery-feedback/analytics")
def pm_delivery_feedback_analytics(claims: dict = Depends(auth.require_pm)):
    """Aggregate-only view (rating distribution + compliment rate) for the
    Delivery Feedback tab — no raw compliment text, just the numbers."""
    return npstore.compute_delivery_feedback_breakdown()


@nykaa_router.get("/pm/brand-breakdown")
def pm_brand_breakdown(period_type: str = "monthly", period_key: str | None = None, claims: dict = Depends(auth.require_pm)):
    return {"brands": nykaa_insights.brand_breakdown(period_type, period_key)}


@nykaa_router.get("/pm/category-breakdown")
def pm_category_breakdown(period_type: str = "monthly", period_key: str | None = None, claims: dict = Depends(auth.require_pm)):
    return {"categories": nykaa_insights.category_breakdown(period_type, period_key)}


@nykaa_router.get("/pm/weekly-report")
def pm_weekly_report(period_type: str = "weekly", period_key: str | None = None, claims: dict = Depends(auth.require_pm)):
    return nykaa_insights.generate_brand_report(period_type, period_key)


@nykaa_router.get("/pm/brand-scorecards")
def pm_brand_scorecards(period_type: str = "monthly", period_key: str | None = None, claims: dict = Depends(auth.require_pm)):
    """Phase 4 "brand scorecards" — one short AI-written line per brand,
    layered on top of the same brand_breakdown numbers the Brands tab table
    already shows."""
    brand_rows = nykaa_insights.brand_breakdown(period_type, period_key)
    return {"scorecards": nykaa_ai_features.generate_brand_scorecards(brand_rows)}
