"""AI analysis for the PM insights pipeline: sentiment, category, theme,
urgency, and whether a piece of customer voice actually needs a human to
act on it.

This is a different lens than classifier.py's TicketClassification, which
answers "which team should handle this and how urgently" for routing.
feedback_ai answers "what is the customer feeling, what is it about, and is
there anything actionable here at all" — applied uniformly across every
source of customer voice (ticket, review, survey), not just tickets. A
ticket still goes through classifier.py exactly as before; this is an
independent, additional read on the same text.

Same reliability shape as classifier.py: a strict JSON Schema enforced at
the API level (see llm_providers.py), one repair turn if that still comes
back unparseable/invalid, then a deterministic keyword-based fallback so a
result is always produced — API outage, no configured provider, or a
truly malformed response should never surface as an error to the caller.
"""
import json
import time
from dataclasses import dataclass

from pydantic import ValidationError

from . import llm_providers as llm
from .models import CATEGORY_THEMES, FeedbackAnalysis, FeedbackCategory, SentimentLabel


def _format_category_themes() -> str:
    return "\n".join(f'  - "{category}": {", ".join(themes)}' for category, themes in CATEGORY_THEMES.items())


SYSTEM_PROMPT = f"""You are a senior feedback analyst on a cosmetics/beauty e-commerce company's CX \
analytics team. You read one piece of customer voice at a time — a support ticket, a product review, or \
a survey response — and turn it into structured signal for a Product Manager's dashboard. Treat all \
three the same way: read what the customer actually said and report on it. You are not routing or \
resolving anything, and you are not the one deciding what to build — you are the analyst giving an \
accurate, unbiased read of this one item.

Rules:
- category is EXACTLY one of these 10 fixed categories — never invent a new one, never rename or reword them:
  - "Product Quality & Fit": the product itself underperforming for this customer — wrong shade, didn't suit their skin/hair type, weak fragrance, short shelf life, inconsistent formula between batches.
  - "Packaging & Damage": something wrong with how the product arrived, not the formula — leaked, broken seal, tampered packaging, cracked container, an item missing from the box.
  - "Delivery & Logistics": the shipment itself — late delivery, wrong item shipped, non-delivery, a lost package, courier behavior. Not the product's condition on arrival (that's Packaging & Damage) or its quality (that's Product Quality & Fit).
  - "Review & App Flow Friction": friction in the app/website while shopping, ordering, or leaving a review — forced fields, a rating that resets, having to re-select a product, a checkout crash, slow loading.
  - "Authenticity & Trust": doubts about whether the product is genuine — suspected counterfeit, a missing safety seal, ingredients that don't match what's listed.
  - "Personalization Mismatch": a personalization/recommendation feature getting it wrong — a beauty-profile-style feature that doesn't match the customer's stated attributes, an irrelevant recommendation, an inaccurate shade finder.
  - "Pricing & Offers": cost matters — a coupon that didn't apply, a price drop right after buying, hidden charges, a slow refund, whether it's "worth it".
  - "Rewards & Loyalty": loyalty/rewards mechanics specifically — points not credited, a review stuck in moderation past the promised window, unclear tier benefits.
  - "Customer Support": how a support interaction itself felt — slow response, an unhelpful agent, a ticket that took forever to resolve, or genuinely helpful support.
  - "General Praise / Other": pure positive feedback with no specific feature or problem attached, OR the text is blank/near-empty/spam/mixed feedback with nothing specific enough to act on.
  Use "General Praise / Other" only for those two cases above — never as a shortcut when a real, specific \
topic is present; in that case pick whichever of the other 9 it's actually about, even if it touches \
more than one (pick the most dominant/specific one).
- theme is a specific sub-topic within the category you picked — prefer one of the reference themes listed \
below for that category, but if none of them accurately fit, write a new short, specific theme name (2-4 \
words) instead of forcing a bad fit. Never leave it as something generic like "General" when the text is \
specific enough to name the actual sub-topic.
  Reference themes per category:
{_format_category_themes()}
- sentiment_label is the customer's overall feeling about their experience — exactly one of positive, \
neutral, or negative. Judge it from the words used, not the topic — a calm question about a technical \
detail is neutral, not negative, even if the underlying topic (a refund, a safety concern) sounds serious. \
When a message contains both praise and criticism, classify by what's actually dominant and actionable \
rather than splitting the difference: a concrete, unresolved problem being reported — even softened by \
real praise elsewhere in the same message — is negative, because the problem is what needs attention. \
Praise paired with only minor, passing criticism is positive. Only classify neutral when it's genuinely \
balanced with nothing concrete to act on either way (calm pros and cons, no real complaint).
- sentiment_score is a finer-grained number for the same judgment, and doubles as your confidence in it: \
-1 (fully confident negative) to 1 (fully confident positive), 0 being genuine, low-confidence \
neutrality. It must agree in direction with sentiment_label — don't contradict your own label.
- urgency_score is 0 (no urgency, can wait indefinitely) to 1 (needs attention right now) — driven by \
severity and business impact (a safety/allergic-reaction concern, a suspected counterfeit, a customer \
about to churn), not by politeness or exclamation points.
- is_actionable_ticket is true only if a human/team genuinely needs to do something in response — a \
real product defect, a delivery problem, a billing dispute, a safety concern, a support request. It is \
false for praise, general venting with no specific ask, or commentary where there's nothing to act on \
(e.g. "I love this brand" or "just wanted to say thanks"). A negative sentiment does not automatically \
mean actionable — "I've shopped here for years and I'm just disappointed things have changed" is \
negative but has nothing concrete to act on either.
- reasoning is one sentence, specific to this item's content.
- The text may be in any language. Understand it in its original language, but always write \
`reasoning` in English (category/theme are already constrained/guided to English names above).
- A blank, near-empty, or meaningless message gets: sentiment_label=neutral, sentiment_score=0, \
category="General Praise / Other", theme="Insufficient Detail", urgency_score=0, is_actionable_ticket=false.

Worked examples, one per category plus two extra edge cases for the combined last category, for \
calibration — not a lookup table for real inputs:
1. "The Fit Me foundation oxidized within an hour and turned three shades darker than what I picked online." -> \
sentiment_label=negative, sentiment_score=-0.6, category="Product Quality & Fit", theme="Formula Issue", \
urgency_score=0.3, is_actionable_ticket=true. Reasoning: the formula performing differently than expected \
on skin, not a shipping or packaging problem.
2. "The sunscreen bottle arrived with the pump completely broken and half the product had already leaked into the box." -> \
sentiment_label=negative, sentiment_score=-0.7, category="Packaging & Damage", theme="Leaked in Transit", \
urgency_score=0.5, is_actionable_ticket=true. Reasoning: physical damage to the packaging during shipping \
caused product loss.
3. "My order was supposed to arrive four days ago and the tracking hasn't updated since it left the warehouse." -> \
sentiment_label=negative, sentiment_score=-0.5, category="Delivery & Logistics", theme="Late Delivery", \
urgency_score=0.4, is_actionable_ticket=true. Reasoning: a shipment that's overdue with no tracking movement.
4. "I rated the first product in my order, but when I went to rate the second one my first rating had disappeared and I had to redo it." -> \
sentiment_label=negative, sentiment_score=-0.4, category="Review & App Flow Friction", \
theme="Rating Reset Mid-Order", urgency_score=0.3, is_actionable_ticket=true. Reasoning: a state-loss bug \
in the multi-item review flow.
5. "The seal on this palette looked different from the one I got last time and the packaging print felt slightly off — is this even genuine?" -> \
sentiment_label=negative, sentiment_score=-0.5, category="Authenticity & Trust", \
theme="Suspected Counterfeit", urgency_score=0.6, is_actionable_ticket=true. Reasoning: the customer \
suspects the product isn't genuine based on packaging differences.
6. "I filled out my skin profile as oily and acne-prone but it keeps recommending heavy, creamy moisturizers that don't fit that at all." -> \
sentiment_label=negative, sentiment_score=-0.4, category="Personalization Mismatch", \
theme="Irrelevant Recommendation", urgency_score=0.2, is_actionable_ticket=true. Reasoning: the \
personalization profile isn't producing recommendations that match the stated skin type.
7. "I used a valid coupon code at checkout but the discount never applied to my final total." -> \
sentiment_label=negative, sentiment_score=-0.4, category="Pricing & Offers", theme="Coupon Not Applied", \
urgency_score=0.3, is_actionable_ticket=true. Reasoning: a working coupon code failing to apply its discount.
8. "It's been two weeks since my review was approved and I still haven't received the reward points I was promised." -> \
sentiment_label=negative, sentiment_score=-0.4, category="Rewards & Loyalty", theme="Points Not Credited", \
urgency_score=0.3, is_actionable_ticket=true. Reasoning: promised loyalty points that never arrived after approval.
9. "I've messaged support three times about the same issue this week and keep getting copy-pasted replies that don't address my question." -> \
sentiment_label=negative, sentiment_score=-0.6, category="Customer Support", theme="Unhelpful Agent", \
urgency_score=0.4, is_actionable_ticket=true. Reasoning: repeated unhelpful support responses to the same \
unresolved question.
10. "Honestly this brand has never let me down, everything I've ordered has been exactly as described." -> \
sentiment_label=positive, sentiment_score=0.8, category="General Praise / Other", theme="Reliable Brand", \
urgency_score=0.0, is_actionable_ticket=false. Reasoning: pure praise with no specific feature or problem attached.
11. "meh" -> sentiment_label=neutral, sentiment_score=0.0, category="General Praise / Other", \
theme="Insufficient Detail", urgency_score=0.0, is_actionable_ticket=false. Reasoning: too little content \
to identify any topic or actionable request.
12. "I've shopped here for years and I'm just a bit disappointed things aren't quite what they used to be." -> \
sentiment_label=negative, sentiment_score=-0.3, category="General Praise / Other", theme="Mixed Feedback", \
urgency_score=0.1, is_actionable_ticket=false. Reasoning: general disappointment with nothing specific to \
any category to act on."""

# Hand-written rather than FeedbackAnalysis.model_json_schema(), same reason
# as classifier.TICKET_SCHEMA: output_config.format rejects some JSON Schema
# keywords Pydantic emits (minimum/maximum, etc.) — range/length checks still
# happen client-side via the FeedbackAnalysis model below. theme is a plain
# string (no enum) — a JSON Schema can't cleanly enforce "valid for this
# category" as a cross-field constraint across all 3 providers' strict
# schema support, so the prompt guides it instead (see CATEGORY_THEMES).
FEEDBACK_SCHEMA = {
    "type": "object",
    "properties": {
        "sentiment_label": {"type": "string", "enum": [s.value for s in SentimentLabel]},
        "sentiment_score": {"type": "number"},
        "category": {"type": "string", "enum": [c.value for c in FeedbackCategory]},
        "theme": {"type": "string"},
        "urgency_score": {"type": "number"},
        "is_actionable_ticket": {"type": "boolean"},
        "reasoning": {"type": "string"},
    },
    "required": [
        "sentiment_label", "sentiment_score", "category", "theme", "urgency_score",
        "is_actionable_ticket", "reasoning",
    ],
    "additionalProperties": False,
}

# A single AI call classifying a whole chunk of texts at once — used only by
# the one-off reclassification/backfill scripts (see analyze_feedback_batch).
BATCH_FEEDBACK_SCHEMA = {
    "type": "object",
    "properties": {"items": {"type": "array", "items": FEEDBACK_SCHEMA}},
    "required": ["items"],
    "additionalProperties": False,
}

BATCH_SYSTEM_PROMPT_SUFFIX = """

You will be given a numbered list of separate, unrelated feedback items in one message. Analyze each one \
independently — do not let one item's content influence another's classification. Return exactly one \
result per input item, inside the required "items" array, in the same order you were given them — never \
skip, merge, or reorder items, and never return more or fewer results than you were given."""

_NEGATIVE_WORDS = ["hate", "terrible", "awful", "worst", "broken", "damaged", "leaked", "expired",
                   "counterfeit", "fake", "allergic", "angry", "frustrated", "disappointed",
                   "unacceptable", "refund", "cancel", "scam"]
_POSITIVE_WORDS = ["love", "great", "awesome", "excellent", "thanks", "thank you", "amazing", "helpful", "reliable"]
_URGENT_WORDS = ["urgent", "immediately", "asap", "allergic reaction", "safety", "counterfeit",
                  "tampered", "can't access", "hacked"]

# Deterministic, best-effort keyword -> fixed-category mapping for the
# offline fallback path (no provider configured / every AI attempt failed).
# Checked in order, first match wins; this doesn't need the nuance of the
# LLM, just a reasonable guess so the fallback never has to invent a category.
_CATEGORY_KEYWORDS: list[tuple[FeedbackCategory, list[str]]] = [
    (FeedbackCategory.AUTHENTICITY_TRUST, ["counterfeit", "fake product", "not genuine", "tampered", "seal missing"]),
    (FeedbackCategory.PACKAGING_DAMAGE, ["leaked", "leaking", "broken seal", "cracked", "damaged in transit", "spilled"]),
    (FeedbackCategory.DELIVERY_LOGISTICS, ["delivery", "delayed", "late", "courier", "shipment", "tracking", "never arrived", "lost package"]),
    (FeedbackCategory.PRICING_OFFERS, ["price", "pricing", "coupon", "discount", "billing", "invoice", "charge", "refund", "cost"]),
    (FeedbackCategory.REWARDS_LOYALTY, ["reward points", "loyalty", "moderation", "points not credited", "tier"]),
    (FeedbackCategory.PERSONALIZATION_MISMATCH, ["recommendation", "beauty portfolio", "shade finder", "personalization", "doesn't suit my skin"]),
    (FeedbackCategory.CUSTOMER_SUPPORT, ["support", "reply", "response", "customer service", "agent"]),
    (FeedbackCategory.REVIEW_APP_FLOW_FRICTION, ["app crash", "checkout", "rating reset", "slow loading", "freeze", "glitch", "bug"]),
    (FeedbackCategory.PRODUCT_QUALITY_FIT, ["shade", "wrong color", "didn't suit", "expired", "fragrance", "formula", "allergic", "reaction"]),
]


def _keyword_category(lowered: str) -> FeedbackCategory:
    for category, keywords in _CATEGORY_KEYWORDS:
        if any(kw in lowered for kw in keywords):
            return category
    return FeedbackCategory.GENERAL_PRAISE_OTHER


@dataclass
class FeedbackOutcome:
    analysis: FeedbackAnalysis
    mode: str
    model_used: str
    latency_ms: int


def _keyword_fallback(text: str) -> FeedbackAnalysis:
    """Deterministic, offline fallback — mirrors baseline.py's role for
    ticket classification: no network call, always available, deliberately
    simple. Used when no provider is configured, or every AI attempt fails."""
    lowered = text.lower().strip()
    if not lowered:
        return FeedbackAnalysis(
            sentiment_label=SentimentLabel.NEUTRAL, sentiment_score=0.0,
            category=FeedbackCategory.GENERAL_PRAISE_OTHER, theme="Insufficient Detail",
            urgency_score=0.0, is_actionable_ticket=False,
            reasoning="Empty input.",
        )

    neg_hits = [w for w in _NEGATIVE_WORDS if w in lowered]
    pos_hits = [w for w in _POSITIVE_WORDS if w in lowered]
    urgent_hits = [w for w in _URGENT_WORDS if w in lowered]

    if neg_hits and pos_hits:
        # Same rule as the AI prompt: a real complaint alongside praise still
        # reads as negative — the complaint is the actionable part.
        label, score = SentimentLabel.NEGATIVE, -0.2
    elif neg_hits:
        label, score = SentimentLabel.NEGATIVE, -0.6
    elif pos_hits:
        label, score = SentimentLabel.POSITIVE, 0.6
    else:
        label, score = SentimentLabel.NEUTRAL, 0.0

    category = _keyword_category(lowered)
    theme = CATEGORY_THEMES[category.value][0]
    urgency = 0.8 if urgent_hits else (0.4 if neg_hits else 0.0)
    actionable = bool(neg_hits or urgent_hits)

    return FeedbackAnalysis(
        sentiment_label=label, sentiment_score=score, category=category, theme=theme,
        urgency_score=urgency, is_actionable_ticket=actionable,
        reasoning="Keyword-based fallback (no live AI analysis available).",
    )


def _run_provider(provider: str, client, text: str) -> FeedbackOutcome:
    start = time.monotonic()
    model_used = llm.PROVIDER_MODEL[provider]
    transient_errors = llm.transient_errors_for(provider)

    try:
        if provider == "anthropic":
            response = llm.call_anthropic(client, text, SYSTEM_PROMPT, FEEDBACK_SCHEMA, repair=False)
            if response.stop_reason == "refusal":
                raise ValueError("model refused to analyze this feedback")
            raw = next((b.text for b in response.content if b.type == "text"), "")
        else:
            call = llm.call_openai if provider == "openai" else llm.call_groq
            response = call(client, text, SYSTEM_PROMPT, FEEDBACK_SCHEMA, repair=False)
            if response.choices[0].finish_reason == "content_filter":
                raise ValueError("model refused to analyze this feedback")
            raw = response.choices[0].message.content or ""

        data = llm.extract_json(raw)
        if data is None:
            raise ValueError("could not parse JSON from first response")
        analysis = FeedbackAnalysis.model_validate(data)
        mode = "live"

    except (ValueError, ValidationError, json.JSONDecodeError):
        try:
            if provider == "anthropic":
                repaired = llm.call_anthropic(client, text, SYSTEM_PROMPT, FEEDBACK_SCHEMA, repair=True, prior_content=response.content)
                raw = next((b.text for b in repaired.content if b.type == "text"), "")
            else:
                call = llm.call_openai if provider == "openai" else llm.call_groq
                repaired = call(client, text, SYSTEM_PROMPT, FEEDBACK_SCHEMA, repair=True, prior_text=response.choices[0].message.content or "")
                raw = repaired.choices[0].message.content or ""

            data = llm.extract_json(raw)
            if data is None:
                raise ValueError("repair attempt still not parseable")
            analysis = FeedbackAnalysis.model_validate(data)
            mode = "repaired"
        except Exception:
            analysis = _keyword_fallback(text)
            mode = "fallback"

    except transient_errors:
        analysis = _keyword_fallback(text)
        mode = "fallback"

    latency_ms = int((time.monotonic() - start) * 1000)
    return FeedbackOutcome(analysis, mode, model_used if mode in ("live", "repaired") else "keyword-baseline", latency_ms)


def analyze_feedback(text: str) -> FeedbackOutcome:
    """Analyze one piece of customer voice — the single entry point used by
    every ingestion path (ticket mirroring, review/survey import). category
    is constrained by FEEDBACK_SCHEMA to one of the fixed FeedbackCategory
    values; theme is free text guided toward CATEGORY_THEMES."""
    start = time.monotonic()
    providers = llm.available_providers()
    if not providers:
        result = _keyword_fallback(text)
        return FeedbackOutcome(result, "mock", "keyword-baseline", int((time.monotonic() - start) * 1000))
    provider = providers[0]
    return _run_provider(provider, llm.get_client(provider), text)


def _run_batch(provider: str, client, texts: list[str]) -> list[FeedbackAnalysis] | None:
    """One AI call for a whole chunk. Returns None (never raises) if the
    response can't be parsed/validated or its item count doesn't match the
    input — the caller falls back to per-item keyword classification for
    the chunk rather than attempting a repair turn, since this path is only
    used by one-off maintenance scripts, not live traffic."""
    message = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(texts))
    try:
        if provider == "anthropic":
            response = llm.call_anthropic(client, message, SYSTEM_PROMPT + BATCH_SYSTEM_PROMPT_SUFFIX, BATCH_FEEDBACK_SCHEMA, repair=False)
            if response.stop_reason == "refusal":
                return None
            raw = next((b.text for b in response.content if b.type == "text"), "")
        else:
            call = llm.call_openai if provider == "openai" else llm.call_groq
            response = call(client, message, SYSTEM_PROMPT + BATCH_SYSTEM_PROMPT_SUFFIX, BATCH_FEEDBACK_SCHEMA, repair=False)
            if response.choices[0].finish_reason == "content_filter":
                return None
            raw = response.choices[0].message.content or ""

        data = llm.extract_json(raw)
        if not data or len(data.get("items", [])) != len(texts):
            return None
        return [FeedbackAnalysis.model_validate(item) for item in data["items"]]
    except Exception:
        return None


def analyze_feedback_batch(texts: list[str]) -> list[FeedbackOutcome]:
    """Classify a whole chunk of feedback texts (the caller chunks into
    groups of ~8) with a single AI call instead of one call per item —
    used only by the one-off reclassification/backfill maintenance scripts,
    which need to process hundreds of rows without hundreds of round trips.
    Live ingestion (analyze_feedback) stays one-at-a-time: real feedback
    arrives one submission at a time, so there's nothing to batch there.

    Falls back to per-item _keyword_fallback for the whole chunk if the
    batch call fails or comes back malformed — no repair turn, since this
    is a maintenance path, not user-facing."""
    if not texts:
        return []
    start = time.monotonic()
    providers = llm.available_providers()
    if not providers:
        return [FeedbackOutcome(_keyword_fallback(t), "mock", "keyword-baseline", 0) for t in texts]

    provider = providers[0]
    client = llm.get_client(provider)
    analyses = _run_batch(provider, client, texts)
    latency_ms = int((time.monotonic() - start) * 1000) // max(len(texts), 1)

    if analyses is None:
        return [FeedbackOutcome(_keyword_fallback(t), "fallback", "keyword-baseline", latency_ms) for t in texts]

    model_used = llm.PROVIDER_MODEL[provider]
    return [FeedbackOutcome(a, "live", model_used, latency_ms) for a in analyses]
