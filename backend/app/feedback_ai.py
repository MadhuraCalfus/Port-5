"""AI analysis for the PM insights pipeline: sentiment, theme, urgency, and
whether a piece of customer voice actually needs a human to act on it.

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
import re
import time
from dataclasses import dataclass

from pydantic import ValidationError

from . import llm_providers as llm
from .models import FeedbackAnalysis, SentimentLabel

SYSTEM_PROMPT = """You analyze one piece of customer voice for a product/CX analytics pipeline. \
The text may be a support ticket, a product review, or a survey response — treat all three the \
same way: read what the customer actually said and report on it, you are not routing or resolving \
anything.

Rules:
- sentiment_label is the customer's overall feeling about their experience: positive, neutral, \
negative, or mixed (genuinely both — e.g. loves the product but hates one specific thing). Judge it \
from the words used, not the topic — a calm question about a technical detail is neutral, not \
negative, even if the underlying topic (billing, security) sounds serious.
- sentiment_score is a finer-grained number for the same judgment: -1 (as negative as it gets) to \
1 (as positive as it gets), 0 being genuinely neutral. It should agree with sentiment_label \
(negative label -> negative score, etc.) — don't contradict your own label.
- theme is the single most specific, concrete label for what this is actually about — 2-4 words, \
like "checkout latency", "duplicate billing charge", or "dark mode bug". Never use a generic bucket \
like "customer issues", "bad experience", "app problems", or "general feedback" — if you're tempted \
to write something that vague, look again at the text for the specific thing being described. If the \
text truly gives you nothing specific to name (e.g. it's blank or says only "bad"), use "insufficient \
detail" rather than inventing specificity that isn't there.
- urgency_score is 0 (no urgency, can wait indefinitely) to 1 (needs attention right now) — driven by \
severity and business impact (data loss, security, an outage, a customer about to churn), not by \
politeness or exclamation points.
- is_actionable_ticket is true only if a human/team genuinely needs to do something in response — a \
real bug, a billing dispute, a security concern, a support request. It is false for praise, general \
venting with no specific ask, or commentary where there's nothing to act on (e.g. "I love this app" \
or "just wanted to say thanks"). A negative sentiment does not automatically mean actionable — \
"I've been a customer for years and I'm just disappointed things have changed" is negative but has \
nothing concrete to act on either.
- reasoning is one sentence, specific to this item's content.
- The text may be in any language. Understand it in its original language, but always write \
`reasoning` and `theme` in English.
- A blank, near-empty, or meaningless message still gets a full result: sentiment_label=neutral, \
sentiment_score=0, theme="insufficient detail", urgency_score=0, is_actionable_ticket=false.

Worked examples, for calibration — chosen to cover the distinctions above (positive-but-not-actionable, \
negative-but-not-actionable, mixed sentiment, and the vague/empty edge case), not to hand you a lookup \
table for real inputs:
1. "I was charged twice for my subscription this month and support hasn't replied in a week." -> \
sentiment_label=negative, sentiment_score=-0.7, theme="duplicate billing charge", urgency_score=0.7, \
is_actionable_ticket=true. Reasoning: a real, unresolved billing dispute with a concrete ask.
2. "Just wanted to say the new dashboard redesign looks great, really clean." -> sentiment_label=positive, \
sentiment_score=0.8, theme="dashboard redesign praise", urgency_score=0.0, is_actionable_ticket=false. \
Reasoning: positive feedback with no request or problem to act on.
3. "Love the app overall but the export button has been broken for two weeks now." -> \
sentiment_label=mixed, sentiment_score=-0.1, theme="broken export button", urgency_score=0.5, \
is_actionable_ticket=true. Reasoning: genuine praise paired with a specific, still-unfixed defect.
4. "meh" -> sentiment_label=neutral, sentiment_score=0.0, theme="insufficient detail", \
urgency_score=0.0, is_actionable_ticket=false. Reasoning: too little content to identify any specific \
topic or actionable request."""

# Hand-written rather than FeedbackAnalysis.model_json_schema(), same reason
# as classifier.TICKET_SCHEMA: output_config.format rejects some JSON Schema
# keywords Pydantic emits (minimum/maximum, etc.) — range/length checks still
# happen client-side via the FeedbackAnalysis model below.
FEEDBACK_SCHEMA = {
    "type": "object",
    "properties": {
        "sentiment_label": {"type": "string", "enum": [s.value for s in SentimentLabel]},
        "sentiment_score": {"type": "number"},
        "theme": {"type": "string"},
        "urgency_score": {"type": "number"},
        "is_actionable_ticket": {"type": "boolean"},
        "reasoning": {"type": "string"},
    },
    "required": [
        "sentiment_label", "sentiment_score", "theme", "urgency_score",
        "is_actionable_ticket", "reasoning",
    ],
    "additionalProperties": False,
}

_NEGATIVE_WORDS = ["hate", "terrible", "awful", "worst", "broken", "bug", "crash", "angry",
                   "frustrated", "disappointed", "unacceptable", "refund", "cancel", "scam"]
_POSITIVE_WORDS = ["love", "great", "awesome", "excellent", "thanks", "thank you", "amazing", "helpful"]
_URGENT_WORDS = ["urgent", "immediately", "asap", "down", "can't access", "lost my data", "security", "hacked"]


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
            theme="insufficient detail", urgency_score=0.0, is_actionable_ticket=False,
            reasoning="Empty input.",
        )

    neg_hits = [w for w in _NEGATIVE_WORDS if w in lowered]
    pos_hits = [w for w in _POSITIVE_WORDS if w in lowered]
    urgent_hits = [w for w in _URGENT_WORDS if w in lowered]

    if neg_hits and pos_hits:
        label, score = SentimentLabel.MIXED, -0.1
    elif neg_hits:
        label, score = SentimentLabel.NEGATIVE, -0.6
    elif pos_hits:
        label, score = SentimentLabel.POSITIVE, 0.6
    else:
        label, score = SentimentLabel.NEUTRAL, 0.0

    theme = f"keyword match: {neg_hits[0] if neg_hits else pos_hits[0]}" if (neg_hits or pos_hits) else "insufficient detail"
    urgency = 0.8 if urgent_hits else (0.4 if neg_hits else 0.0)
    actionable = bool(neg_hits or urgent_hits)

    return FeedbackAnalysis(
        sentiment_label=label, sentiment_score=score, theme=theme,
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
    every ingestion path (ticket mirroring, review/survey import)."""
    start = time.monotonic()
    providers = llm.available_providers()
    if not providers:
        result = _keyword_fallback(text)
        return FeedbackOutcome(result, "mock", "keyword-baseline", int((time.monotonic() - start) * 1000))
    provider = providers[0]
    return _run_provider(provider, llm.get_client(provider), text)
