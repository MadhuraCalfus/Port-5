"""LLM-powered ticket classification with schema enforcement and a repair path.

Design notes (also covered in the README):
- We hand the model a strict JSON Schema (Claude's `output_config.format`
  Structured Outputs, OpenAI's `response_format` json_schema strict mode, or
  Groq's `response_format` JSON mode). That constrains the *shape* of the
  response at the API level, so "the model forgot a field" or "the model
  wrapped it in markdown" mostly can't happen. This is the primary answer to
  "how do you handle malformed JSON" — you prevent most of it before it
  happens.
- We still don't trust it blindly. `llm_providers.extract_json` and the repair turn below
  are a second line of defense for the cases structured outputs doesn't fully
  cover: a refusal, a truncated response (`max_tokens`), or a transient
  response that fails our own Pydantic validation (e.g. confidence outside
  0-1). One repair turn is attempted before we give up and fall back to the
  rule-based baseline so the user always gets *something* usable.
- Three providers are supported, in preference order: Anthropic (Claude) >
  OpenAI > Groq. Anthropic and OpenAI both have strict schema enforcement;
  Groq's is weaker (JSON mode, not a strict schema), which is exactly what
  the repair path above already exists to cover. Whichever providers are
  configured, `classify_ticket` uses the first as the primary result; when a
  caller asks to compare, `classify_with_all_providers` runs the *same*
  ticket through every configured provider so they can be shown side by side.
- The multi-provider client/call/JSON-recovery plumbing itself lives in
  `llm_providers.py`, shared with `feedback_ai.py` (the PM insights
  pipeline) — this module only owns the ticket-routing prompt, schema, and
  the classify/suggest orchestration built on top of that shared plumbing.
"""
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from pydantic import ValidationError

from . import baseline, llm_providers as llm
from .models import Category, Priority, ResolutionSuggestion, Team, Tone, TicketClassification

MODEL = llm.MODEL
PROVIDER_MODEL = llm.PROVIDER_MODEL
PROVIDER_PRIORITY = llm.PROVIDER_PRIORITY

SYSTEM_PROMPT = """You are the triage engine for a company's support ticket routing system. \
You read one incoming support message and decide how it should be routed.

Category -> team routing. Use this mapping — don't improvise a different team for a given category:
- Billing -> Billing Support
- Technical Issue -> Technical Support
- Account Access -> Account Management
- Bug Report -> Engineering
- Feature Request -> Product Team
- Complaint -> Customer Success
- Security Concern -> Security Team
- General Inquiry -> Customer Success
- Triage is reserved for the rare case where no category above genuinely fits, or the message is too short or empty to tell what's wrong — always pair team=Triage with category=General Inquiry, low confidence, and is_ambiguous=true. Never use Triage just because a ticket is hard; pick the best real category/team first.

Category definitions. Technical Issue, Bug Report, and Account Access are the three easiest to confuse — read these carefully:
- Technical Issue: the product or infrastructure isn't performing as expected for reasons outside one specific defect — slow, down, timing out, sync/integration/API failures.
- Bug Report: a specific, reproducible defect in the software's own behavior — a crash, an error message, wrong output, a broken UI element — the kind of thing a developer would file and fix.
- Account Access: can't log in, locked out, forgot password, MFA/2FA or sign-in trouble specifically.
- Billing: money matters — charges, invoices, refunds, subscriptions, payment methods, pricing/plan changes.
- Feature Request: the customer is asking for functionality that doesn't exist yet.
- Complaint: dissatisfaction with the service or experience where there's no specific technical fault to diagnose — service quality, policy, a pricing change, general disappointment.
- Security Concern: anything suggesting compromise — hacking, phishing, unauthorized or unrecognized access, leaked or exposed data.
- General Inquiry: everything else, including genuinely unclear or near-empty messages.

Rules:
- Always choose exactly one category, priority, and team, even if the ticket is short, vague, \
sarcastic, or touches more than one issue. Never refuse to classify a ticket just because it's \
ambiguous — pick your best answer and say so via is_ambiguous instead.
- If a ticket clearly touches more than one issue, classify by whichever one the customer seems to care about most (mentioned first, or most emphasized) and set is_ambiguous=true to flag that a second issue is also present — don't split the difference between two categories or two teams.
- Set is_ambiguous=true whenever the ticket could reasonably fit more than one category, or there \
is not enough information to be confident.
- confidence is how sure you are in THIS classification (0 = pure guess, 1 = certain), not how \
important the ticket is.
- tone is the customer's emotional state as written (neutral, frustrated, angry, urgent, confused, \
worried, positive) - judge it from the actual words used, not the topic, and not from how short or \
detailed the message is. worried is anxiety about a possible bad outcome ("is this normal?", "I'm \
concerned my data was exposed", "I hope this isn't serious") — distinct from confused (the \
customer's own words show they don't understand something, e.g. "why is this happening?" or "I \
don't get it") and urgent (wants faster action); it shows up often, but not exclusively, on Security \
Concern tickets. A short or vague message is not automatically confused — a terse, flat statement \
like "unable to login" or "app is slow" is neutral tone with low information, not confused tone; \
only use confused when the customer's wording itself expresses not understanding something.
- reasoning must be exactly one sentence, specific to this ticket's content.
- The ticket may be written in any language. Understand it in its original language, but always \
write `reasoning` in English, regardless of what language the ticket itself is in.
- Priority guidance: judge priority from objective severity only — security concerns, data loss, \
and outages that stop the customer from working are High; routine billing/account/technical \
issues are Medium; cosmetic issues, feature requests, and calm general questions are Low. Ignore \
urgency-signaling words and formatting (e.g. "urgent", "ASAP", "immediately", "now", ALL CAPS, \
exclamation points, angry language) when deciding priority — pretend the ticket was written in a \
flat, calm voice and rate priority on the underlying issue alone. A separate rule outside your \
control already handles raising priority to High when tone is frustrated, angry, or urgent, so do \
not do it yourself.
- A one-word or near-empty message should still be classified: default toward General Inquiry / \
Triage with low confidence and is_ambiguous=true, and use reasoning to say what's missing.

Worked examples, for calibration — match this style and level of specificity in your own reasoning, not these exact words:
1. "I noticed a login from a country I don't recognize, can someone check this? I hope my account is okay." -> category=Security Concern, priority=High, team=Security Team, tone=worried, confidence=0.9, is_ambiguous=false. Reasoning: an unrecognized login location suggests possible unauthorized account access, and the customer expresses concern rather than anger.
2. "This is ridiculous!! The dark mode toggle resets every single time I refresh the page!!!" -> category=Bug Report, priority=Low, team=Engineering, tone=angry, confidence=0.85, is_ambiguous=false. Reasoning: a cosmetic UI settings bug, regardless of how angrily it's phrased.
3. "not working" -> category=General Inquiry, priority=Low, team=Triage, tone=neutral, confidence=0.3, is_ambiguous=true. Reasoning: the message doesn't say what isn't working or which part of the product is affected, but nothing in the wording itself expresses confusion, so tone stays neutral.
4. "I was double-charged for my subscription and the app also keeps crashing when I export data" -> category=Billing, priority=Medium, team=Billing Support, tone=frustrated, confidence=0.6, is_ambiguous=true. Reasoning: two distinct issues are reported; the billing dispute is treated as primary since it's mentioned first."""

# The schema the model must fill in. Deliberately hand-written (rather than
# Category.model_json_schema()) because output_config.format rejects a
# handful of JSON Schema keywords Pydantic likes to emit (minimum/maximum,
# etc. — see the Structured Outputs limitations in the API docs). Confidence
# is still range-checked, just client-side, via TicketClassification below.
# Shared by all three providers — Claude's output_config.format, OpenAI's
# response_format, and Groq's response_format all accept a plain JSON Schema.
TICKET_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": [c.value for c in Category]},
        "priority": {"type": "string", "enum": [p.value for p in Priority]},
        "team": {"type": "string", "enum": [t.value for t in Team]},
        "tone": {"type": "string", "enum": [t.value for t in Tone]},
        "confidence": {"type": "number"},
        "is_ambiguous": {"type": "boolean"},
        "reasoning": {"type": "string"},
    },
    "required": ["category", "priority", "team", "tone", "confidence", "is_ambiguous", "reasoning"],
    "additionalProperties": False,
}

SUGGESTION_SYSTEM_PROMPT = """You are a friendly customer support assistant. A customer describes \
an issue before it's ever routed to a human support team, and your job is to try to help them \
solve it themselves right now, without waiting for a human — a real human still reviews it \
afterward regardless, so it's fine to say "I'm not sure" rather than force an answer.

Rules:
- If you can plausibly help, give 2-5 concrete, actionable steps the customer can try themselves \
right now. Steps must be specific to what they actually described — never generic filler like \
"restart the app" unless it's genuinely relevant to this issue.
- Set can_likely_self_resolve=false (and keep steps short or empty) whenever a human really should \
handle it instead: billing disputes/refunds, security incidents or suspected account compromise, \
anything involving lost data, or a message with too little information to say anything concrete.
- Never invent account-specific facts (their balance, their plan, whether something is a known bug \
on our end) — only offer general troubleshooting a customer could try on their own.
- summary is one short sentence naming what you think the underlying issue is.
- Match the language the customer wrote in."""

# Same JSON-Schema-enforcement approach as ticket classification (see the
# module docstring) — just a different shape, since this isn't a routing
# decision.
SUGGESTION_SCHEMA = {
    "type": "object",
    "properties": {
        "can_likely_self_resolve": {"type": "boolean"},
        "summary": {"type": "string"},
        "steps": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["can_likely_self_resolve", "summary", "steps"],
    "additionalProperties": False,
}


def mode_info() -> dict:
    return llm.mode_info()


def repair_demo(broken_json: str) -> dict:
    """Deterministic demonstration of the repair path, independent of any
    live API call — lets you show a mentor exactly what happens when the
    model returns garbage, without waiting on network flakiness to trigger it."""
    recovered = llm.extract_json(broken_json)
    return {
        "input": broken_json,
        "recovered": recovered,
        "success": recovered is not None,
    }


def _escalate(priority: Priority, tone: Tone) -> tuple[Priority, bool]:
    if tone in (Tone.FRUSTRATED, Tone.ANGRY, Tone.URGENT) and priority == Priority.MEDIUM:
        return Priority.HIGH, True
    return priority, False


@dataclass
class ClassifyOutcome:
    classification: TicketClassification
    mode: str
    model_used: str
    latency_ms: int


def _baseline_as_classification(message: str) -> TicketClassification:
    b = baseline.classify(message)
    return TicketClassification(
        category=b.category,
        priority=b.priority,
        team=b.team,
        tone=b.tone,
        confidence=0.4,
        is_ambiguous=True,
        reasoning=b.reasoning,
    )


def _run_provider(provider: str, client, message: str) -> ClassifyOutcome:
    """Run one ticket through one provider's structured-output call, with the
    shared extract/validate/repair/fallback pipeline. Used both for the
    single primary classification and for side-by-side model comparison."""
    start = time.monotonic()
    model_used = PROVIDER_MODEL[provider]
    transient_errors = llm.transient_errors_for(provider)

    try:
        if provider == "anthropic":
            response = llm.call_anthropic(client, message, SYSTEM_PROMPT, TICKET_SCHEMA, repair=False)
            if response.stop_reason == "refusal":
                raise ValueError("model refused to classify this ticket")
            text = next((b.text for b in response.content if b.type == "text"), "")
        else:
            call = llm.call_openai if provider == "openai" else llm.call_groq
            response = call(client, message, SYSTEM_PROMPT, TICKET_SCHEMA, repair=False)
            if response.choices[0].finish_reason == "content_filter":
                raise ValueError("model refused to classify this ticket")
            text = response.choices[0].message.content or ""

        data = llm.extract_json(text)
        if data is None:
            raise ValueError("could not parse JSON from first response")
        classification = TicketClassification.model_validate(data)
        mode = "live"

    except (ValueError, ValidationError, json.JSONDecodeError):
        # Repair path: give the model one chance to fix its own output.
        try:
            if provider == "anthropic":
                repaired = llm.call_anthropic(client, message, SYSTEM_PROMPT, TICKET_SCHEMA, repair=True, prior_content=response.content)
                text = next((b.text for b in repaired.content if b.type == "text"), "")
            else:
                call = llm.call_openai if provider == "openai" else llm.call_groq
                repaired = call(client, message, SYSTEM_PROMPT, TICKET_SCHEMA, repair=True, prior_text=response.choices[0].message.content or "")
                text = repaired.choices[0].message.content or ""

            data = llm.extract_json(text)
            if data is None:
                raise ValueError("repair attempt still not parseable")
            classification = TicketClassification.model_validate(data)
            mode = "repaired"
        except Exception:
            classification = _baseline_as_classification(message)
            mode = "fallback"

    except transient_errors:
        # Network/quota trouble — degrade gracefully instead of a 500.
        classification = _baseline_as_classification(message)
        mode = "fallback"

    latency_ms = int((time.monotonic() - start) * 1000)
    return ClassifyOutcome(classification, mode, model_used if mode in ("live", "repaired") else "keyword-baseline", latency_ms)


def classify_ticket(message: str) -> ClassifyOutcome:
    """Classify using only the single highest-priority configured provider —
    the fast, cheap path used whenever a multi-model comparison isn't asked for."""
    start = time.monotonic()
    providers = llm.available_providers()
    if not providers:
        result = _baseline_as_classification(message)
        return ClassifyOutcome(result, "mock", "keyword-baseline", int((time.monotonic() - start) * 1000))
    provider = providers[0]
    return _run_provider(provider, llm.get_client(provider), message)


def classify_with_all_providers(message: str) -> list[tuple[str, ClassifyOutcome]]:
    """Run the *same* ticket through every configured live provider, so their
    answers can be shown side by side. Returns [] in mock mode (nothing to
    compare)."""
    providers = llm.available_providers()
    return [(p, _run_provider(p, llm.get_client(p), message)) for p in providers]


def suggest_resolution(message: str) -> dict:
    """Best-effort self-service suggestion shown to the customer before a
    ticket is ever created. Unlike classify_ticket, there's no keyword-based
    fallback that makes sense here — if this fails, isn't configured, or the
    model can't help, the customer just proceeds straight to raising a real
    ticket, so a single attempt with no repair turn is proportionate to how
    much this feature actually matters."""
    providers = llm.available_providers()
    if not providers:
        return {"available": False, "can_likely_self_resolve": False, "summary": None, "steps": []}

    provider = providers[0]
    client = llm.get_client(provider)
    try:
        if provider == "anthropic":
            response = llm.call_anthropic(client, message, SUGGESTION_SYSTEM_PROMPT, SUGGESTION_SCHEMA, repair=False)
            if response.stop_reason == "refusal":
                raise ValueError("model declined to help with this")
            text = next((b.text for b in response.content if b.type == "text"), "")
        else:
            call = llm.call_openai if provider == "openai" else llm.call_groq
            response = call(client, message, SUGGESTION_SYSTEM_PROMPT, SUGGESTION_SCHEMA, repair=False)
            if response.choices[0].finish_reason == "content_filter":
                raise ValueError("model declined to help with this")
            text = response.choices[0].message.content or ""

        data = llm.extract_json(text)
        if data is None:
            raise ValueError("could not parse JSON from response")
        suggestion = ResolutionSuggestion.model_validate(data)
        return {
            "available": True,
            "can_likely_self_resolve": suggestion.can_likely_self_resolve,
            "summary": suggestion.summary,
            "steps": suggestion.steps,
        }
    except Exception:
        # Any failure here (parse error, validation error, refusal, network/
        # quota trouble) collapses to the same outcome: no suggestion, and
        # the customer proceeds straight to raising a real ticket.
        return {"available": False, "can_likely_self_resolve": False, "summary": None, "steps": []}


def build_ticket_result(message: str, manual_time_seconds: float | None, compare: bool) -> dict:
    outcomes: list[tuple[str, ClassifyOutcome]] = []
    if compare:
        outcomes = classify_with_all_providers(message)

    primary_outcome = outcomes[0][1] if outcomes else classify_ticket(message)
    c = primary_outcome.classification
    priority, escalated = _escalate(c.priority, c.tone)

    result = {
        "message": message,
        "category": c.category.value,
        "priority": priority.value,
        "team": c.team.value,
        "tone": c.tone.value,
        "confidence": c.confidence,
        "is_ambiguous": c.is_ambiguous,
        "escalated": escalated,
        "reasoning": c.reasoning,
        "model_used": primary_outcome.model_used,
        "mode": primary_outcome.mode,
        "latency_ms": primary_outcome.latency_ms,
        "manual_time_seconds": manual_time_seconds,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    if compare:
        b = baseline.classify(message)
        result["baseline"] = {
            "category": b.category.value,
            "priority": b.priority.value,
            "team": b.team.value,
            "reasoning": b.reasoning,
        }
        if len(outcomes) > 1:
            result["model_results"] = [
                {
                    "provider": provider,
                    "model_used": outcome.model_used,
                    "mode": outcome.mode,
                    "latency_ms": outcome.latency_ms,
                    "category": outcome.classification.category.value,
                    "priority": outcome.classification.priority.value,
                    "team": outcome.classification.team.value,
                    "tone": outcome.classification.tone.value,
                    "confidence": outcome.classification.confidence,
                    "is_ambiguous": outcome.classification.is_ambiguous,
                    "reasoning": outcome.classification.reasoning,
                }
                for provider, outcome in outcomes
            ]

    return result
