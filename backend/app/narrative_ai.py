"""AI-generated plain-language periodic report — the "Weekly Insight" stage
of the PM pipeline. Takes insights.py's trend computation (already-aggregated
numbers, no raw customer text) and turns it into a short report meant to be
readable by anyone — a VP of CX skimming it for the first time, not just the
PM who generated it.

Same reliability shape as classifier.py/feedback_ai.py: strict JSON Schema,
one repair turn on a bad first response. Unlike those, the fallback here
isn't a keyword heuristic — it's a deterministic narrative template built
directly from the same numbers, so "no AI provider configured" still
produces a coherent, readable report rather than an empty one. The report
itself is persisted by the caller (see store.upsert_periodic_insight) so
repeat views of the same period are stable rather than regenerated.
"""
import json

from pydantic import ValidationError

from . import llm_providers as llm
from .models import NarrativeReport

SYSTEM_PROMPT = """You write a short, plain-language periodic report for a product/CX team, based \
entirely on aggregated customer feedback numbers you're given — total volume, sentiment and urgency \
averages and their change from the prior period, and per-theme counts/trends. You are NOT given the \
raw customer text, only these numbers — never invent specifics beyond what's given.

Audience: anyone, not just the person who ran this report — a VP of CX skimming it for the first \
time should understand what happened and what to do, without needing anything explained.

Rules:
- headline is one sentence naming the single most important thing that happened — usually the \
biggest theme or the biggest change, not a generic "here is this period's report."
- key_findings are 3-6 short, specific bullet points — cite actual numbers and theme names from what \
you were given (e.g. "Checkout complaints tripled to 14 mentions, the largest increase this period"), \
never vague filler like "customer sentiment varied."
- narrative is a short paragraph (2-5 sentences) connecting the findings into a coherent story: what \
happened, whether it's better or worse than before, and why it matters.
- bottom_line is the single most actionable next step — specific enough that someone could act on it \
today. If nothing in the data warrants urgent action, say so plainly ("no urgent action needed this \
period — keep monitoring X") rather than inventing urgency that isn't there.
- Never contradict the numbers you were given — if sentiment improved, don't write a headline implying \
things got worse.

Worked examples, for calibration — one clearly worsening period and one calm one, to show both ends \
of the range:
1. Given: 42 items this week (+18 vs last week), avg sentiment -0.35 (down from -0.05), theme \
"checkout latency" at 14 mentions (new, avg urgency 0.75) -> headline="Checkout latency complaints \
surged this week, dragging overall sentiment sharply negative.", key_findings=["Checkout latency \
went from unreported to 14 mentions this week, the single largest theme.", "Average sentiment fell \
from -0.05 to -0.35 week over week.", "Total feedback volume rose 18 items, largely driven by the \
checkout issue."], narrative="This week saw a sharp rise in complaints about checkout latency, which \
appeared from nowhere to become the dominant theme with 14 mentions and high average urgency. That \
single issue is the main driver behind a significant week-over-week drop in overall sentiment.", \
bottom_line="Escalate the checkout latency issue to Engineering immediately and have CX prepare a \
customer-facing status update."
2. Given: 9 items this week (-2 vs last week), avg sentiment 0.20 (up from 0.05), no theme above 3 \
mentions -> headline="A quiet week — feedback volume was low and sentiment continued to improve.", \
key_findings=["Only 9 items this week, down slightly from 11 last week.", "Average sentiment rose \
from 0.05 to 0.20.", "No single theme stood out — the largest had only 3 mentions."], \
narrative="This was a calm period: feedback volume stayed low and sentiment kept trending positive, \
with no theme concentrated enough to flag.", bottom_line="No urgent action needed this week — keep \
monitoring as usual.\""""

NARRATIVE_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "key_findings": {"type": "array", "items": {"type": "string"}},
        "narrative": {"type": "string"},
        "bottom_line": {"type": "string"},
    },
    "required": ["headline", "key_findings", "narrative", "bottom_line"],
    "additionalProperties": False,
}


def _format_trend_for_prompt(trend: dict) -> str:
    current = trend["current"]
    lines = [
        f"Period: {trend['period_type']} {trend['current_period_start']} to {trend['current_period_end']} "
        f"(key {trend['current_period_key']}), compared to the previous period ({trend['previous_period_key']}).",
        f"Total feedback items this period: {current['total_items']} (change vs previous: {trend['total_items_delta']:+d}).",
        f"Actionable items (needing human follow-up): {current['actionable_count']}.",
        f"Average sentiment score: {current['avg_sentiment_score']:+.2f} (change: {trend['avg_sentiment_score_delta']:+.2f}).",
        f"Average urgency score: {current['avg_urgency_score']:.2f} (change: {trend['avg_urgency_score_delta']:+.2f}).",
        f"Sentiment distribution: {current['sentiment_distribution']}.",
        f"Source breakdown: {current['source_breakdown']}.",
        "",
        "Theme changes this period (most notable first):",
    ]
    for d in trend["theme_deltas"][:10]:
        change = "new this period" if d["delta_pct"] is None else f"{d['delta_pct']:+.1f}% vs previous"
        lines.append(f'- "{d["theme"]}": {d["current_count"]} mentions (previous: {d["previous_count"]}), {change}')

    if current["theme_urgency_ranking"]:
        lines.append("")
        lines.append("Top themes by urgency this period:")
        for t in current["theme_urgency_ranking"][:5]:
            lines.append(
                f'- "{t["theme"]}": {t["count"]} mentions, avg urgency {t["avg_urgency_score"]:.2f}, '
                f'avg sentiment {t["avg_sentiment_score"]:.2f}'
            )
    return "\n".join(lines)


def _template_report(trend: dict) -> dict:
    """Deterministic fallback used when no AI provider is configured or every
    live attempt fails — built directly from the same numbers a live call
    would see, so "AI is down" still yields a coherent, specific report."""
    current = trend["current"]
    notable = [d for d in trend["theme_deltas"] if d["direction"] in ("new", "up")][:3]

    if current["total_items"] == 0:
        return {
            "headline": f"No feedback recorded for this {trend['period_type']} period.",
            "key_findings": ["No tickets, reviews, or surveys were logged in this period."],
            "narrative": "There is nothing to report for this period — no customer feedback was recorded.",
            "bottom_line": "No action needed — nothing came in this period.",
        }

    headline = (
        f"{current['total_items']} feedback items this {trend['period_type']} period, "
        f"average sentiment {current['avg_sentiment_score']:+.2f}."
    )
    key_findings = [
        f"Total volume: {current['total_items']} items ({trend['total_items_delta']:+d} vs previous period).",
        f"Average sentiment: {current['avg_sentiment_score']:+.2f} ({trend['avg_sentiment_score_delta']:+.2f} vs previous).",
        f"Average urgency: {current['avg_urgency_score']:.2f}.",
    ]
    for d in notable:
        change = "new this period" if d["delta_pct"] is None else f"{d['delta_pct']:+.1f}%"
        key_findings.append(f'"{d["theme"]}": {d["current_count"]} mentions ({change}).')

    top_theme = notable[0]["theme"] if notable else (current["theme_urgency_ranking"][0]["theme"] if current["theme_urgency_ranking"] else None)
    bottom_line = (
        f'Review "{top_theme}" first — it is the most notable theme this period.'
        if top_theme else "No standout theme this period — no urgent action indicated."
    )

    return {
        "headline": headline,
        "key_findings": key_findings,
        "narrative": (
            "This report was generated without live AI analysis (no provider configured or all "
            "attempts failed), so it reflects the raw numbers directly rather than a written summary."
        ),
        "bottom_line": bottom_line,
    }


def generate_report(trend: dict) -> tuple[dict, str, str]:
    """Returns (report_dict, mode, model_used) — mode is "live"/"repaired"/
    "fallback"/"mock", matching the convention used elsewhere in this app."""
    providers = llm.available_providers()
    if not providers:
        return _template_report(trend), "mock", "keyword-baseline"

    provider = providers[0]
    client = llm.get_client(provider)
    model_used = llm.PROVIDER_MODEL[provider]
    message = _format_trend_for_prompt(trend)
    transient_errors = llm.transient_errors_for(provider)

    try:
        if provider == "anthropic":
            response = llm.call_anthropic(client, message, SYSTEM_PROMPT, NARRATIVE_SCHEMA, repair=False)
            if response.stop_reason == "refusal":
                raise ValueError("model refused to generate this report")
            text = next((b.text for b in response.content if b.type == "text"), "")
        else:
            call = llm.call_openai if provider == "openai" else llm.call_groq
            response = call(client, message, SYSTEM_PROMPT, NARRATIVE_SCHEMA, repair=False)
            if response.choices[0].finish_reason == "content_filter":
                raise ValueError("model refused to generate this report")
            text = response.choices[0].message.content or ""

        data = llm.extract_json(text)
        if data is None:
            raise ValueError("could not parse JSON from first response")
        report = NarrativeReport.model_validate(data)
        return report.model_dump(), "live", model_used

    except (ValueError, ValidationError, json.JSONDecodeError):
        # Repair path: give the model one chance to fix its own output.
        try:
            if provider == "anthropic":
                repaired = llm.call_anthropic(client, message, SYSTEM_PROMPT, NARRATIVE_SCHEMA, repair=True, prior_content=response.content)
                text = next((b.text for b in repaired.content if b.type == "text"), "")
            else:
                call = llm.call_openai if provider == "openai" else llm.call_groq
                repaired = call(client, message, SYSTEM_PROMPT, NARRATIVE_SCHEMA, repair=True, prior_text=response.choices[0].message.content or "")
                text = repaired.choices[0].message.content or ""

            data = llm.extract_json(text)
            if data is None:
                raise ValueError("repair attempt still not parseable")
            report = NarrativeReport.model_validate(data)
            return report.model_dump(), "repaired", model_used
        except Exception:
            return _template_report(trend), "fallback", "keyword-baseline"

    except transient_errors:
        # Network/quota trouble — no `response` to repair from; degrade
        # straight to the deterministic template instead of a 500.
        return _template_report(trend), "fallback", "keyword-baseline"
