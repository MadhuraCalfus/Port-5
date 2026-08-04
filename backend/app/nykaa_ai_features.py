"""Nykaa Pulse — Phase 4 AI feature layer, mapped directly to the teardown's
own "AI & LLM-Powered Feature Opportunities" section:
- brand scorecards ("PM / analytics automation")
- a per-product review summary, a scoped-down "fit summarizer" — the
  teardown's version cross-references a Beauty-Portfolio skin/hair profile
  this build doesn't implement, so this instead summarizes plain consensus
  across a product's own published reviews (falling back to the product's
  seed positive/negative theme tags when there isn't a live AI provider or
  there simply aren't reviews yet)
- "ask the reviews" — grounded Q&A over one product's review corpus

Same reliability shape as actions_ai.py throughout: a single
best-effort LLM attempt with a deterministic fallback, not a full repair-turn
pipeline — these enhance the dashboard/catalog, nothing else in the app
depends on their output.
"""
import time

from . import baseline, llm_providers as llm
from .models import Category, Priority, Team, Tone

# ---------------------------------------------------------------------------
# Brand scorecards
# ---------------------------------------------------------------------------

SCORECARD_SYSTEM_PROMPT = """You write one-sentence brand scorecards for a beauty/cosmetics product manager, \
based on aggregated review numbers per brand. You are NOT given raw review text, only these numbers — never \
invent specifics beyond what's given.

Rules:
- One scorecard sentence per brand you're given, in the same order, naming that exact brand.
- Cite the brand's actual numbers in plain language — average rating (if any), how many reviews, and the single \
most common theme if there is a clearly dominant one. Never cite raw sentiment counts or scores verbatim.
- Keep it genuinely short: one sentence, no more — like "Rating steady at 4.2, but shade mismatch complaints are \
up." Never a full paragraph.
- Match tone to the numbers: a brand with strong ratings and no notable complaints gets a positive or neutral \
sentence, not a manufactured concern.

Worked example:
Brand "Maybelline", count=6, avg_rating=4.1, sentiment_counts={"positive": 4, "neutral": 1, "negative": 1}, \
top_theme="Shade Mismatch" -> scorecard="Rating holding at 4.1 across 6 reviews; the one recurring complaint is shade mismatch."
"""

SCORECARD_SCHEMA = {
    "type": "object",
    "properties": {
        "scorecards": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"brand": {"type": "string"}, "scorecard": {"type": "string"}},
                "required": ["brand", "scorecard"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["scorecards"],
    "additionalProperties": False,
}


def _fallback_scorecard(row: dict) -> str:
    rating_part = f"avg rating {row['avg_rating']:.1f}" if row.get("avg_rating") is not None else "no star ratings yet"
    top_theme = row["themes"][0]["theme"] if row.get("themes") else None
    theme_part = f"; top theme: {top_theme}" if top_theme else ""
    return f"{rating_part.capitalize()} across {row['count']} review{'s' if row['count'] != 1 else ''}{theme_part}."


def generate_brand_scorecards(brand_rows: list[dict]) -> dict[str, str]:
    """One LLM call for every brand at once (not one call per brand) —
    brand_rows is nykaa_insights.brand_breakdown()'s own output (its
    `category` field holds the brand name, same relabeling used everywhere
    else in nykaa_insights.py). Returns {brand_name: scorecard}, always —
    falls back to a deterministic per-brand line if no provider is
    configured or the call fails."""
    if not brand_rows:
        return {}

    providers = llm.available_providers()
    if not providers:
        return {row["category"]: _fallback_scorecard(row) for row in brand_rows}

    message = "\n".join(
        f'Brand "{row["category"]}", count={row["count"]}, avg_rating={row["avg_rating"]}, '
        f'sentiment_counts={row["sentiment_counts"]}, '
        f'top_theme={row["themes"][0]["theme"] if row.get("themes") else None}'
        for row in brand_rows
    )
    provider = providers[0]
    client = llm.get_client(provider)
    try:
        if provider == "anthropic":
            response = llm.call_anthropic(client, message, SCORECARD_SYSTEM_PROMPT, SCORECARD_SCHEMA, repair=False)
            if response.stop_reason == "refusal":
                raise ValueError("model refused")
            text = next((b.text for b in response.content if b.type == "text"), "")
        else:
            call = llm.call_openai if provider == "openai" else llm.call_groq
            response = call(client, message, SCORECARD_SYSTEM_PROMPT, SCORECARD_SCHEMA, repair=False)
            if response.choices[0].finish_reason == "content_filter":
                raise ValueError("model refused")
            text = response.choices[0].message.content or ""

        data = llm.extract_json(text)
        if data is None:
            raise ValueError("could not parse JSON")
        by_brand = {item["brand"]: item["scorecard"] for item in data["scorecards"]}
        # Any brand the model dropped still gets a scorecard, deterministically.
        for row in brand_rows:
            by_brand.setdefault(row["category"], _fallback_scorecard(row))
        return by_brand
    except Exception:
        return {row["category"]: _fallback_scorecard(row) for row in brand_rows}


# ---------------------------------------------------------------------------
# Product review summary — a scoped-down "fit summarizer"
# ---------------------------------------------------------------------------

SUMMARY_SYSTEM_PROMPT = """You summarize what customers are actually saying about one cosmetics product, based \
entirely on its published reviews. Only say what the reviews actually support — never invent a specific \
compliment or complaint nobody made.

Rules:
- summary is 1-2 plain sentences a shopper would find genuinely useful before buying — the overall consensus, \
not a generic restatement of "people like it".
- praise_points and concern_points are each 0-3 short phrases (2-5 words), only included if actually supported \
by the reviews you were given — an empty list is correct when there's nothing to say on that side.
- fit_notes answers "will this suit someone like me" using the skin/hair-type segment breakdown you're given \
(when there is one) — e.g. "Reviewers with oily skin rate this 4.6/5" or "2 of 3 dry-skin reviewers reported \
dryness". Only write a fit_note when a segment actually has enough reviews to say something concrete (the \
breakdown given to you already only includes segments with at least 2 rated reviews) — 0-3 notes, empty list \
is correct when no segment breakdown was given or none of it says anything notable.
- Never mention a specific reviewer or quote anyone directly."""

SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "praise_points": {"type": "array", "items": {"type": "string"}},
        "concern_points": {"type": "array", "items": {"type": "string"}},
        "fit_notes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "praise_points", "concern_points", "fit_notes"],
    "additionalProperties": False,
}


def _review_text(r: dict) -> str | None:
    parts = [p for p in (r.get("review_title"), r.get("review_description")) if p and p.strip()]
    return " — ".join(parts) if parts else None


def _skin_type_segments(reviews: list[dict], min_group_size: int = 2) -> list[dict]:
    """Rating-only aggregation by reviewer skin type — this is the entire
    mechanism behind "reviewers with oily skin rate this 4.6/5": group
    published reviews' star ratings by the reviewer's current Beauty
    Portfolio skin_type, and only surface a group once it has enough rated
    reviews (min_group_size) to say something concrete rather than
    generalizing from one person's rating."""
    by_skin: dict[str, list[int]] = {}
    for r in reviews:
        if r.get("skin_type") and r.get("rating") is not None:
            by_skin.setdefault(r["skin_type"], []).append(r["rating"])
    return [
        {"skin_type": skin, "count": len(ratings), "avg_rating": round(sum(ratings) / len(ratings), 1)}
        for skin, ratings in by_skin.items()
        if len(ratings) >= min_group_size
    ]


def _fallback_product_summary(product: dict, reviews: list[dict]) -> dict:
    """No provider configured, no reviews yet, or the live call failed —
    falls back to the product's own seed positive/negative theme tags
    (real, if generic, ground truth about this specific SKU) plus a purely
    arithmetic version of the skin-type fit notes, no LLM needed for those."""
    segments = _skin_type_segments(reviews)
    fit_notes = [f"Reviewers with {s['skin_type'].lower()} skin rate this {s['avg_rating']}/5 ({s['count']} reviews)." for s in segments]

    if not reviews:
        return {
            "summary": "No published reviews yet for this product.",
            "praise_points": product.get("positive_themes", [])[:3],
            "concern_points": product.get("negative_themes", [])[:3],
            "fit_notes": [],
        }
    positive = product.get("positive_themes") or []
    negative = product.get("negative_themes") or []
    summary = f"Based on {len(reviews)} review{'s' if len(reviews) != 1 else ''}, customers most often mention " + (
        ", ".join(positive[:2]).lower() if positive else "a mix of experiences"
    )
    if negative:
        summary += f", though some report {negative[0].lower()}"
    summary += "."
    return {"summary": summary, "praise_points": positive[:3], "concern_points": negative[:3], "fit_notes": fit_notes}


def summarize_product_reviews(product: dict, reviews: list[dict]) -> dict:
    """reviews: nykaa_store.list_published_reviews_with_profile()'s own
    output — each with rating/review_title/review_description plus the
    reviewer's current skin_type/hair_type (nullable, most reviewers may
    not have a Beauty Portfolio set up yet)."""
    review_texts = [t for t in (_review_text(r) for r in reviews) if t]
    if not review_texts:
        return _fallback_product_summary(product, reviews)
    providers = llm.available_providers()
    if not providers:
        return _fallback_product_summary(product, reviews)

    quotes = "\n".join(f'- "{t}"' for t in review_texts[:20])
    segments = _skin_type_segments(reviews)
    segment_block = (
        "\n\nSkin-type rating breakdown (only segments with 2+ rated reviews):\n"
        + "\n".join(f'- {s["skin_type"]}: avg {s["avg_rating"]}/5 across {s["count"]} reviews' for s in segments)
        if segments
        else "\n\nNo skin-type segment breakdown available (not enough reviewers have a Beauty Portfolio set up yet)."
    )
    message = f'Product: "{product["name"]}"\n\nPublished customer reviews:\n{quotes}{segment_block}'
    provider = providers[0]
    client = llm.get_client(provider)
    try:
        if provider == "anthropic":
            response = llm.call_anthropic(client, message, SUMMARY_SYSTEM_PROMPT, SUMMARY_SCHEMA, repair=False)
            if response.stop_reason == "refusal":
                raise ValueError("model refused")
            text = next((b.text for b in response.content if b.type == "text"), "")
        else:
            call = llm.call_openai if provider == "openai" else llm.call_groq
            response = call(client, message, SUMMARY_SYSTEM_PROMPT, SUMMARY_SCHEMA, repair=False)
            if response.choices[0].finish_reason == "content_filter":
                raise ValueError("model refused")
            text = response.choices[0].message.content or ""

        data = llm.extract_json(text)
        if data is None:
            raise ValueError("could not parse JSON")
        return data
    except Exception:
        return _fallback_product_summary(product, reviews)


# ---------------------------------------------------------------------------
# Ask the reviews — grounded Q&A over one product's review corpus
# ---------------------------------------------------------------------------

QA_SYSTEM_PROMPT = """A shopper is asking a specific question about a cosmetics product before buying it. Answer \
using ONLY the customer reviews you're given for this product — never fall back on general knowledge about the \
product, brand, or ingredients beyond what these specific reviews say.

Rules:
- If the reviews actually address the question, answer it directly and concisely (1-3 sentences), synthesizing \
across reviews rather than quoting one verbatim.
- If the reviews don't say anything relevant to the question, set grounded=false and answer honestly along the \
lines of "the reviews for this product don't mention that" — never guess or use outside knowledge to fill the gap.
- Never invent a specific fact (an ingredient, a claim, a number) that isn't actually stated in the reviews."""

QA_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "grounded": {"type": "boolean"},
    },
    "required": ["answer", "grounded"],
    "additionalProperties": False,
}


def answer_review_question(product_name: str, review_texts: list[str], question: str) -> dict:
    """Returns {answer, grounded, available} — available=False only means
    "no AI provider configured", distinct from grounded=False (AI ran, but
    the reviews genuinely don't address the question)."""
    if not review_texts:
        return {"answer": "There aren't any published reviews for this product yet to answer that from.", "grounded": False, "available": True}

    providers = llm.available_providers()
    if not providers:
        return {"answer": "Ask-the-reviews isn't available right now (no AI provider configured).", "grounded": False, "available": False}

    quotes = "\n".join(f'- "{t}"' for t in review_texts[:20])
    message = f'Product: "{product_name}"\nShopper question: "{question}"\n\nPublished customer reviews:\n{quotes}'
    provider = providers[0]
    client = llm.get_client(provider)
    try:
        if provider == "anthropic":
            response = llm.call_anthropic(client, message, QA_SYSTEM_PROMPT, QA_SCHEMA, repair=False)
            if response.stop_reason == "refusal":
                raise ValueError("model refused")
            text = next((b.text for b in response.content if b.type == "text"), "")
        else:
            call = llm.call_openai if provider == "openai" else llm.call_groq
            response = call(client, message, QA_SYSTEM_PROMPT, QA_SCHEMA, repair=False)
            if response.choices[0].finish_reason == "content_filter":
                raise ValueError("model refused")
            text = response.choices[0].message.content or ""

        data = llm.extract_json(text)
        if data is None:
            raise ValueError("could not parse JSON")
        return {**data, "available": True}
    except Exception:
        return {"answer": "Something went wrong answering that — please try again.", "grounded": False, "available": True}


# ---------------------------------------------------------------------------
# Multi-turn support chat with escalation
# ---------------------------------------------------------------------------

CHAT_TURN_SYSTEM_PROMPT = """You are a friendly Nykaa Pulse customer support assistant, chatting live with a \
customer about one specific order item. You're given a Context line naming that order/product, the conversation \
so far, and the customer's newest message.

Rules:
- The chat is already scoped to one order and product — never ask the customer for their order number or which \
product they mean, you already have it from the Context line.
- Try to actually help first: answer questions (where's my order, how do I use this product, what's the return \
window), ask one concrete clarifying question if you need more detail, or suggest a specific next step — never \
generic filler like "please try restarting" unless it's genuinely relevant.
- Never set escalate=true for small talk, a general-knowledge question, or anything unrelated to this order or a \
real product/service problem — just answer it yourself (or say plainly that you can't help with that) and keep \
escalate=false. A human team should only ever be looped in for a genuine order/product/service issue.
- Set escalate=true (and stop trying to help further) whenever the issue needs a refund, a replacement, a \
physical inspection of the product, or is something conversation alone genuinely can't resolve — this includes \
a damaged/broken/leaking/spoiled product, a suspected counterfeit, a payment/billing dispute, or a customer who \
is clearly still stuck after your own prior replies in this conversation.
- When escalate=true, also set category/priority/team/tone as a human router would, so the ticket can be handed \
off immediately without asking the customer to repeat themselves — reasoning explains briefly why you escalated.
- When escalate=false, set category/priority/team to empty strings "" and tone to "neutral" — they're unused.
- reply is what the customer sees directly, written to them — not a description of your reasoning. When \
escalating, reply should tell them you're connecting them to the right team, in plain warm language.
- Match the language the customer wrote in."""

CHAT_TURN_SCHEMA = {
    "type": "object",
    "properties": {
        "reply": {"type": "string"},
        "escalate": {"type": "boolean"},
        "category": {"type": "string", "enum": [c.value for c in Category] + [""]},
        "priority": {"type": "string", "enum": [p.value for p in Priority] + [""]},
        "team": {"type": "string", "enum": [t.value for t in Team] + [""]},
        "tone": {"type": "string", "enum": [t.value for t in Tone]},
        "reasoning": {"type": "string"},
    },
    "required": ["reply", "escalate", "category", "priority", "team", "tone", "reasoning"],
    "additionalProperties": False,
}


def _format_chat_history(history: list[dict], new_message: str, context: str | None = None) -> str:
    lines = [f"Context: {context}"] if context else []
    lines += [f'{"Customer" if turn["role"] == "user" else "Assistant"}: {turn["text"]}' for turn in history]
    lines.append(f"Customer: {new_message}")
    return "\n".join(lines)


def _fallback_chat_turn(new_message: str) -> dict:
    """No provider configured, or the live call (plus its one repair
    attempt) both failed — degrades to an immediate, honest escalation via
    the same deterministic keyword baseline classifier.py's own fallback
    uses, rather than pretending to keep chatting with no real AI behind
    it. Getting a human involved is always a safe default; silently
    stalling the customer is not."""
    b = baseline.classify(new_message)
    return {
        "reply": "Let me connect you with our support team so they can look into this properly.",
        "escalate": True,
        "category": b.category.value,
        "priority": b.priority.value,
        "team": b.team.value,
        "tone": b.tone.value,
        "confidence": 0.4,
        "is_ambiguous": True,
        "reasoning": b.reasoning,
        "model_used": "keyword-baseline",
    }


def run_chat_turn(history: list[dict], new_message: str, context: str | None = None) -> dict:
    """One structured-output LLM call per turn. `history` is prior
    np_chat_turns rows shaped like {"role": "user"|"bot", "text": ...};
    `new_message` is the customer's latest message; `context` is a short
    factual line about which order/product this chat is scoped to (so the
    model doesn't ask the customer for their own order number). Returns a
    dict with reply/escalate plus category/priority/team/tone/confidence/
    is_ambiguous/reasoning/model_used/mode/latency_ms — when escalate is
    True, everything but `reply` is already shaped exactly like classifier.
    build_ticket_result()'s output, so nykaa_store.create_np_ticket can
    consume it directly with no second classification call."""
    start = time.monotonic()
    providers = llm.available_providers()
    if not providers:
        return {**_fallback_chat_turn(new_message), "mode": "mock", "latency_ms": int((time.monotonic() - start) * 1000)}

    provider = providers[0]
    client = llm.get_client(provider)
    message = _format_chat_history(history, new_message, context)
    transient_errors = llm.transient_errors_for(provider)
    response = None

    try:
        if provider == "anthropic":
            response = llm.call_anthropic(client, message, CHAT_TURN_SYSTEM_PROMPT, CHAT_TURN_SCHEMA, repair=False)
            if response.stop_reason == "refusal":
                raise ValueError("model refused")
            text = next((b.text for b in response.content if b.type == "text"), "")
        else:
            call = llm.call_openai if provider == "openai" else llm.call_groq
            response = call(client, message, CHAT_TURN_SYSTEM_PROMPT, CHAT_TURN_SCHEMA, repair=False)
            if response.choices[0].finish_reason == "content_filter":
                raise ValueError("model refused")
            text = response.choices[0].message.content or ""

        data = llm.extract_json(text)
        if data is None:
            raise ValueError("could not parse JSON from first response")
        mode = "live"
    except transient_errors:
        return {**_fallback_chat_turn(new_message), "mode": "fallback", "latency_ms": int((time.monotonic() - start) * 1000)}
    except Exception:
        # Repair path: give the model one chance to fix its own output.
        try:
            if provider == "anthropic":
                repaired = llm.call_anthropic(
                    client, message, CHAT_TURN_SYSTEM_PROMPT, CHAT_TURN_SCHEMA, repair=True, prior_content=response.content
                )
                text = next((b.text for b in repaired.content if b.type == "text"), "")
            else:
                call = llm.call_openai if provider == "openai" else llm.call_groq
                repaired = call(
                    client, message, CHAT_TURN_SYSTEM_PROMPT, CHAT_TURN_SCHEMA, repair=True,
                    prior_text=response.choices[0].message.content or "",
                )
                text = repaired.choices[0].message.content or ""
            data = llm.extract_json(text)
            if data is None:
                raise ValueError("repair attempt still not parseable")
            mode = "repaired"
        except Exception:
            return {**_fallback_chat_turn(new_message), "mode": "fallback", "latency_ms": int((time.monotonic() - start) * 1000)}

    latency_ms = int((time.monotonic() - start) * 1000)
    return {
        "reply": data["reply"],
        "escalate": data["escalate"],
        "category": data["category"] or None,
        "priority": data["priority"] or None,
        "team": data["team"] or None,
        "tone": data["tone"],
        "confidence": 0.8 if mode == "live" else 0.6,
        "is_ambiguous": False,
        "reasoning": data["reasoning"],
        "model_used": llm.PROVIDER_MODEL[provider],
        "mode": mode,
        "latency_ms": latency_ms,
    }


# ---------------------------------------------------------------------------
# Short titles — ticket issue summary, review title auto-fill
# ---------------------------------------------------------------------------

TICKET_SUMMARY_SYSTEM_PROMPT = """You write a one-sentence title naming a customer support ticket's actual issue, \
based on the full chat transcript between the customer and the support bot.

Rules:
- One short sentence (under 12 words), plain language, naming the specific problem — like "Serum bottle arrived \
broken and leaking" or "Wrong shade delivered, wants a replacement" — never a vague restatement like "customer has an issue."
- Base it only on what the customer actually said — never invent a detail that isn't in the transcript.
- No quotation marks, no trailing period."""

TICKET_SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {"title": {"type": "string"}},
    "required": ["title"],
    "additionalProperties": False,
}


def _fallback_title(text: str, max_len: int = 60) -> str:
    """No provider configured, or the call failed — truncate at a word
    boundary rather than mid-word."""
    text = " ".join(text.split())
    if len(text) <= max_len:
        return text
    return text[:max_len].rsplit(" ", 1)[0] + "…"


def fallback_ticket_title(transcript: str) -> str:
    """The same instant, no-LLM-call title summarize_ticket_issue falls back
    to when no provider is configured or the live call fails — exposed
    separately so a caller on a customer's synchronous wait path (chat_turn's
    escalation) can use this immediately instead of paying for a second LLM
    round-trip just for a display title, and backfill the nicer AI-written
    one afterward via a background task."""
    first_customer_line = next((line[10:] for line in transcript.splitlines() if line.startswith("Customer: ")), transcript)
    return _fallback_title(first_customer_line)


def summarize_ticket_issue(transcript: str) -> str:
    """One short line naming the customer's actual issue, for Admin's ticket
    table — `message` on np_tickets keeps the raw transcript for
    classification/audit, this is purely a display title."""
    providers = llm.available_providers()
    if not providers:
        return fallback_ticket_title(transcript)

    provider = providers[0]
    client = llm.get_client(provider)
    try:
        if provider == "anthropic":
            response = llm.call_anthropic(client, transcript, TICKET_SUMMARY_SYSTEM_PROMPT, TICKET_SUMMARY_SCHEMA, repair=False)
            if response.stop_reason == "refusal":
                raise ValueError("model refused")
            text = next((b.text for b in response.content if b.type == "text"), "")
        else:
            call = llm.call_openai if provider == "openai" else llm.call_groq
            response = call(client, transcript, TICKET_SUMMARY_SYSTEM_PROMPT, TICKET_SUMMARY_SCHEMA, repair=False)
            if response.choices[0].finish_reason == "content_filter":
                raise ValueError("model refused")
            text = response.choices[0].message.content or ""

        data = llm.extract_json(text)
        if data is None:
            raise ValueError("could not parse JSON")
        return data["title"]
    except Exception:
        return fallback_ticket_title(transcript)


REVIEW_TITLE_SYSTEM_PROMPT = """You write a short, punchy review title (under 8 words) summarizing a customer's \
product review, based on its description text — like "Great for sensitive skin" or "Arrived damaged, disappointed." \
Base it only on what the review description actually says. No quotation marks, no trailing period."""

REVIEW_TITLE_SCHEMA = {
    "type": "object",
    "properties": {"title": {"type": "string"}},
    "required": ["title"],
    "additionalProperties": False,
}


def summarize_review_title(description: str) -> str:
    """Auto-fills a review's title from its description when the customer
    left the title blank — real Nykaa forces both fields; this app doesn't."""
    providers = llm.available_providers()
    if not providers:
        return _fallback_title(description, max_len=40)

    provider = providers[0]
    client = llm.get_client(provider)
    try:
        if provider == "anthropic":
            response = llm.call_anthropic(client, description, REVIEW_TITLE_SYSTEM_PROMPT, REVIEW_TITLE_SCHEMA, repair=False)
            if response.stop_reason == "refusal":
                raise ValueError("model refused")
            text = next((b.text for b in response.content if b.type == "text"), "")
        else:
            call = llm.call_openai if provider == "openai" else llm.call_groq
            response = call(client, description, REVIEW_TITLE_SYSTEM_PROMPT, REVIEW_TITLE_SCHEMA, repair=False)
            if response.choices[0].finish_reason == "content_filter":
                raise ValueError("model refused")
            text = response.choices[0].message.content or ""

        data = llm.extract_json(text)
        if data is None:
            raise ValueError("could not parse JSON")
        return data["title"]
    except Exception:
        return _fallback_title(description, max_len=40)



# ---------------------------------------------------------------------------
# Beauty routine generator
# ---------------------------------------------------------------------------

ROUTINE_SYSTEM_PROMPT = """You build a personalized skincare routine and haircare routine for a shopper, based on \
their beauty profile. For EACH step listed below you're given 1-3 real candidate products, already ranked so an \
exact skin/hair type match beats a concern-keyword match beats plain popularity (see each candidate's matched_on). \
Pick exactly ONE candidate per step — by its exact product_id from that step's own list only, never a product_id \
from a different step, never an invented one — and write a short reason (one sentence, under 20 words) that names \
the SPECIFIC match reason (their actual skin/hair type, a named concern, or its rating) rather than a generic \
compliment. Two shoppers with different profiles should generally get different products and different reasons \
for the same step — don't write interchangeable reasons.

Return exactly one entry per step listed, in the same order, for both routines."""

ROUTINE_SCHEMA = {
    "type": "object",
    "properties": {
        "skincare_picks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"product_id": {"type": "integer"}, "reason": {"type": "string"}},
                "required": ["product_id", "reason"],
                "additionalProperties": False,
            },
        },
        "haircare_picks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"product_id": {"type": "integer"}, "reason": {"type": "string"}},
                "required": ["product_id", "reason"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["skincare_picks", "haircare_picks"],
    "additionalProperties": False,
}

_MATCH_REASON = {
    "type": "A great match for your specific type.",
    "concern": "Chosen to help with one of your noted concerns.",
    "popularity": "Highly rated by other customers.",
}


def _fallback_routine_section(steps: list[dict]) -> list[dict]:
    """No provider configured, or the call failed — each step's own
    already-best-sorted first candidate (exact type match, then concern
    match, then popularity), so the routine is still complete, just
    without AI-written reasoning."""
    out = []
    for entry in steps:
        candidates = entry["candidates"]
        if not candidates:
            continue
        top = candidates[0]
        out.append({
            "step": entry["step"], "product_id": top["product_id"], "product_name": top["product_name"],
            "reason": _MATCH_REASON.get(top["matched_on"], _MATCH_REASON["popularity"]),
        })
    return out


def _fallback_routine(routine_candidates: dict) -> dict:
    return {
        "skincare_routine": _fallback_routine_section(routine_candidates.get("skincare", [])),
        "haircare_routine": _fallback_routine_section(routine_candidates.get("haircare", [])),
    }


def _apply_picks(steps: list[dict], picks: list[dict]) -> list[dict]:
    """Zips the model's per-step picks back onto our own step labels/order.
    The model only ever chose among the candidates handed to it for that
    exact step, so a missing/hallucinated/out-of-list product_id just
    falls back to that step's own top candidate instead of breaking."""
    out = []
    for i, entry in enumerate(steps):
        candidates = entry["candidates"]
        if not candidates:
            continue
        by_id = {c["product_id"]: c for c in candidates}
        pick = picks[i] if i < len(picks) else None
        candidate = by_id.get((pick or {}).get("product_id")) or candidates[0]
        reason = (pick or {}).get("reason") or _MATCH_REASON.get(candidate["matched_on"], _MATCH_REASON["popularity"])
        out.append({
            "step": entry["step"], "product_id": candidate["product_id"],
            "product_name": candidate["product_name"], "reason": reason,
        })
    return out


def generate_beauty_routine(profile: dict, routine_candidates: dict) -> dict:
    """`routine_candidates` (see nykaa_store.compute_routine_candidates) is a
    fixed set of canonical steps per routine (Cleanser/Serum/Moisturizer/
    Sunscreen for skincare; Shampoo/Conditioner/Hair Oil/Styling for
    haircare), each already populated with real, ranked candidates from
    that step's own subcategory — every subcategory has products
    regardless of review history, so a routine is always fully populated.
    Returns {skincare_routine, haircare_routine}, each a list of
    {step, product_id, product_name, reason}."""
    skincare_steps = routine_candidates.get("skincare", [])
    haircare_steps = routine_candidates.get("haircare", [])
    if not any(s["candidates"] for s in skincare_steps) and not any(s["candidates"] for s in haircare_steps):
        return {"skincare_routine": [], "haircare_routine": []}

    providers = llm.available_providers()
    if not providers:
        return _fallback_routine(routine_candidates)

    profile_line = (
        f"Skin type: {profile.get('skin_type') or 'not specified'}. "
        f"Skin concerns: {', '.join(profile.get('skin_concerns') or []) or 'not specified'}. "
        f"Hair type: {profile.get('hair_type') or 'not specified'}. "
        f"Scalp type: {profile.get('scalp_type') or 'not specified'}. "
        f"Hair concerns: {', '.join(profile.get('hair_concerns') or []) or 'not specified'}."
    )

    def _step_lines(steps: list[dict]) -> str:
        lines = [
            f'- {entry["step"]}: ' + "; ".join(
                f'id={c["product_id"]} "{c["product_name"]}" by {c["brand"]} '
                f'(matched_on={c["matched_on"]}, avg_rating={c["avg_rating"]})'
                for c in entry["candidates"]
            )
            for entry in steps if entry["candidates"]
        ]
        return "\n".join(lines) if lines else "(no candidates)"

    message = (
        f"Shopper profile: {profile_line}\n\n"
        f"Skincare routine steps and candidates:\n{_step_lines(skincare_steps)}\n\n"
        f"Haircare routine steps and candidates:\n{_step_lines(haircare_steps)}"
    )

    provider = providers[0]
    client = llm.get_client(provider)
    try:
        if provider == "anthropic":
            response = llm.call_anthropic(client, message, ROUTINE_SYSTEM_PROMPT, ROUTINE_SCHEMA, repair=False)
            if response.stop_reason == "refusal":
                raise ValueError("model refused")
            text = next((b.text for b in response.content if b.type == "text"), "")
        else:
            call = llm.call_openai if provider == "openai" else llm.call_groq
            response = call(client, message, ROUTINE_SYSTEM_PROMPT, ROUTINE_SCHEMA, repair=False)
            if response.choices[0].finish_reason == "content_filter":
                raise ValueError("model refused")
            text = response.choices[0].message.content or ""

        data = llm.extract_json(text)
        if data is None:
            raise ValueError("could not parse JSON")
        return {
            "skincare_routine": _apply_picks(skincare_steps, data.get("skincare_picks") or []),
            "haircare_routine": _apply_picks(haircare_steps, data.get("haircare_picks") or []),
        }
    except Exception:
        return _fallback_routine(routine_candidates)
