"""AI-generated plain-language periodic report — the "Weekly Insight" stage
of the PM pipeline. Takes insights.py's trend computation (already-aggregated
numbers, no raw customer text) and turns it into a short report meant to be
read by a non-technical manager — a story of the period plus three simple
takeaways (what's going well, the top pain point, a recommendation), never
a data-report shape with headline/bullet-findings/raw-score citations.

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

SYSTEM_PROMPT = """You write a short, plain-language periodic report for a non-technical product/CX \
manager, based entirely on aggregated customer feedback numbers you're given — total volume, sentiment \
and urgency averages and their change from the prior period, and per-category counts/trends. You are NOT \
given the raw customer text, only these numbers — never invent specifics beyond what's given.

Audience: a manager with no analytics background, reading this on a dashboard. Every field is a list of \
short, standalone bullet points (each one sentence or less) — never a paragraph, and never a bullet that \
only makes sense if you read the one before it.

Rules:
- narrative is 2-4 short bullet points telling the story of the period: what happened, whether things \
got better or worse, and why it matters.
- whats_going_well and top_pain_point are each 1-3 short bullet points, and should work in a concrete \
count or percentage where it fits naturally (e.g. "3 customers this week...", "about a third of this \
period's feedback...", "mentioned in 14 of the 42 reports this period") rather than only vague words like \
"a handful" or "a few" — a manager should come away knowing roughly how many people, not just that "some" \
did. whats_going_well covers what's genuinely working — not a forced silver lining; if nothing is clearly \
positive this period, one plain bullet should say so rather than inventing praise. top_pain_point names \
the biggest complaint(s)/concern(s) this period — the thing a manager should know about even if they read \
nothing else.
- Across every field, a plain count or percentage is always welcome when it reads naturally (e.g. "almost \
every review mentioned this" or "ratings averaged about 2 out of 5") — but NEVER cite raw internal scores \
(no "avg_urgency_score", no "sentiment_score of -0.4", no decimal deltas) and never use analyst jargon (no \
"impact tier", "urgency score", "trend direction"). Say the same thing in plain words instead.
- recommendation is 1-3 short bullet points on what to actually do about it — specific enough to act on \
today. If nothing warrants action, one bullet should say so plainly ("no urgent action needed this period \
— keep an eye on X") rather than inventing urgency that isn't there.
- Never contradict the numbers you were given — if sentiment improved, don't imply things got worse.

Worked examples, for calibration — one clearly bad period and one calm, positive one:
1. Given: 42 items this week (+18 vs last week), avg sentiment -0.35 (down from -0.05), category \
"Delivery & Logistics" at 14 mentions (new, avg urgency 0.75) -> narrative=["Feedback this week was \
dominated by frustration over late deliveries.", "It came up in 14 of the 42 reports we received.", \
"Overall mood took a clear turn for the worse compared to last week."], whats_going_well=["A handful of \
customers — about 4 or 5 — still took the time to praise how quickly support replied to their tickets."], \
top_pain_point=["Late deliveries were by far the biggest complaint this week, coming up in a third of all \
feedback and far more than anything else."], recommendation=["Get the delivery delays in front of the \
Order & Delivery Team as a priority fix.", "It's clearly the main thing dragging feedback down right now."]
2. Given: 9 items this week (-2 vs last week), avg sentiment 0.20 (up from 0.05), no category above 3 \
mentions -> narrative=["This was a quiet, calm week — only 9 pieces of feedback came in.", "The overall \
mood stayed positive, with nothing standing out as a widespread problem."], whats_going_well=["Most of the \
9 customers who wrote in this week were happy.", "No single issue came up more than 3 times."], \
top_pain_point=["A few people — 3 out of 9 — mentioned pricing feels a bit high, though it wasn't a common \
complaint."], recommendation=["No urgent action needed this week — just keep an eye on the pricing comments \
in case they become more frequent."]"""

NARRATIVE_SCHEMA = {
    "type": "object",
    "properties": {
        "narrative": {"type": "array", "items": {"type": "string"}},
        "whats_going_well": {"type": "array", "items": {"type": "string"}},
        "top_pain_point": {"type": "array", "items": {"type": "string"}},
        "recommendation": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["narrative", "whats_going_well", "top_pain_point", "recommendation"],
    "additionalProperties": False,
}


def _format_trend_for_prompt(trend: dict) -> str:
    current = trend["current"]
    previous = trend["previous"]
    lines = [
        f"Period: {trend['period_type']} {trend['current_period_start']} to {trend['current_period_end']} "
        f"(key {trend['current_period_key']}), compared to the previous period ({trend['previous_period_key']}).",
        f"Total feedback items this period: {current['total_items']} (change vs previous: {trend['total_items_delta']:+d}).",
        f"Actionable items (needing human follow-up): {current['actionable_count']}.",
        f"Average sentiment score: {current['avg_sentiment_score']:+.2f} (change: {trend['avg_sentiment_score_delta']:+.2f}).",
        f"Average urgency score: {current['avg_urgency_score']:.2f} (change: {trend['avg_urgency_score_delta']:+.2f}).",
        f"Sentiment distribution: {current['sentiment_distribution']}.",
        f"Source breakdown: {current['source_breakdown']}.",
    ]
    if current["rated_count"]:
        prev_rating = previous["avg_rating"]
        rating_change = f", previous period: {prev_rating:.1f}" if prev_rating is not None else " (no rated surveys last period)"
        lines.append(f"Average survey star rating: {current['avg_rating']:.1f}/5 across {current['rated_count']} rated surveys{rating_change}.")
    lines += [
        "",
        "Category changes this period (most notable first):",
    ]
    for d in trend["category_deltas"][:10]:
        change = "new this period" if d["delta_pct"] is None else f"{d['delta_pct']:+.1f}% vs previous"
        lines.append(f'- "{d["category"]}": {d["current_count"]} mentions (previous: {d["previous_count"]}), {change}')

    if current["category_urgency_ranking"]:
        lines.append("")
        lines.append("Top categories by urgency this period:")
        for t in current["category_urgency_ranking"][:5]:
            lines.append(
                f'- "{t["category"]}": {t["count"]} mentions, avg urgency {t["avg_urgency_score"]:.2f}, '
                f'avg sentiment {t["avg_sentiment_score"]:.2f}'
            )
    return "\n".join(lines)


def _template_report(trend: dict) -> dict:
    """Deterministic fallback used when no AI provider is configured or every
    live attempt fails — built directly from the same numbers a live call
    would see, kept in the same plain-language shape (no raw score
    citations) so "AI is down" still reads like the rest of this report."""
    current = trend["current"]

    if current["total_items"] == 0:
        return {
            "narrative": ["Nothing came in this period — no customer feedback was recorded."],
            "whats_going_well": ["There's nothing to report either way this period."],
            "top_pain_point": ["No complaints this period — there simply wasn't any feedback."],
            "recommendation": ["No action needed — just keep watching for next period."],
        }

    positive = current["sentiment_distribution"].get("positive", 0)
    negative = current["sentiment_distribution"].get("negative", 0)
    total = current["total_items"]
    notable = [d for d in trend["category_deltas"] if d["direction"] in ("new", "up") and d["current_count"] > 0]
    top_category = notable[0] if notable else (current["category_urgency_ranking"][0] if current["category_urgency_ranking"] else None)
    top_category_name = top_category["category"] if top_category else None
    top_category_count = top_category.get("current_count") or top_category.get("count") if top_category else None
    mood = "mostly positive" if positive > negative else "mostly negative" if negative > positive else "a mixed bag"
    positive_pct = round(100 * positive / total) if total else 0

    narrative = [f"This period brought in {total} piece{'s' if total != 1 else ''} of feedback, and the overall mood was {mood}."]
    if top_category_name:
        narrative.append(f'The biggest theme was "{top_category_name}."')

    return {
        "narrative": narrative,
        "whats_going_well": [
            f"{positive} piece{'s' if positive != 1 else ''} of feedback this period were positive — "
            f"about {positive_pct}% of everything we heard."
            if positive else "Nothing stood out as clearly positive this period."
        ],
        "top_pain_point": [
            f'"{top_category_name}" was the most notable concern this period, mentioned in '
            f"{top_category_count} piece{'s' if top_category_count != 1 else ''} of feedback."
            if top_category_name and top_category_count
            else f'"{top_category_name}" was the most notable concern this period.'
            if top_category_name
            else "Nothing stood out as a major concern this period."
        ],
        "recommendation": [
            f'Take a look at "{top_category_name}" first — it\'s the most notable theme this period.'
            if top_category_name else "No urgent action needed this period — keep monitoring as usual."
        ],
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
