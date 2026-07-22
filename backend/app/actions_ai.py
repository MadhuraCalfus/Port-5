"""AI-recommended actions for themes that are worsening or already urgent —
the last step in insights.py's trend computation. This module never reads
raw customer text: it takes the aggregated numbers insights.py already
computed (theme, count, trend direction/%, avg urgency, avg sentiment) and
asks the model what a product/CX team should actually do about them.

Which themes are "worth flagging" is decided here with plain arithmetic
(_worth_flagging), not by the model — the model's only job is writing a
good, specific action for a candidate it's handed, not judging severity
itself. Unlike classifier.py/feedback_ai.py, there's no repair turn or
keyword fallback: like suggest_resolution() in classifier.py, this is a
best-effort layer on top of already-solid data, not a core result the rest
of the pipeline depends on, so a single attempt that fails closed to an
empty list is proportionate.
"""
from . import llm_providers as llm
from .models import RecommendedActionsResult

SYSTEM_PROMPT = """You recommend concrete actions for a product/CX team based on trending customer \
feedback themes. You are given a short list of themes that are worsening or already urgent — rising \
in volume, negative in sentiment, or high urgency — each with its current count, trend direction and \
percent change, average sentiment score, and average urgency score. You are NOT given the raw \
customer text, only these aggregated numbers — do not invent specifics you weren't given.

Rules:
- Recommend at most one action per theme you're given — never invent a theme not in the list, and \
never skip a theme you were given without at least a light-touch action.
- action_text must be a concrete, specific action a product or CX team could actually start this \
week — e.g. "escalate checkout latency to Engineering as a sprint priority" or "have CX proactively \
message affected customers with a status update" — never vague filler like "look into this" or \
"investigate further."
- rationale must cite the specific numbers you were given for that theme (the count, the trend \
direction/percent, the urgency and sentiment scores) — not a generic justification that could apply \
to any theme.
- Match the intensity of the action to the severity of the data: a theme with low urgency and only \
mildly negative sentiment gets a lightweight action (monitor, note for next release), not an escalation \
— don't over-escalate everything you're handed just because it made the list.

Worked examples, for calibration — one high-severity and one low-severity, to show the range of \
appropriate intensity:
1. Theme "checkout latency", current_count=14, direction=up, delta_pct=180.0, avg_urgency_score=0.75, \
avg_sentiment_score=-0.6 -> action_text="Escalate checkout latency to Engineering as a sprint priority \
and have CX post a status update to affected customers.", rationale="Volume nearly tripled week over \
week (14, +180%) with high urgency (0.75) and clearly negative sentiment (-0.6) — this is actively \
getting worse, not just noise."
2. Theme "dark mode toggle bug", current_count=3, direction=flat, delta_pct=0.0, avg_urgency_score=0.2, \
avg_sentiment_score=-0.3 -> action_text="Log as a minor bug for the next regular release cycle — no \
immediate escalation needed.", rationale="Low, flat volume (3, unchanged) with low urgency (0.2) — a \
real but low-severity issue, not one that needs urgent action.\""""

ACTIONS_SCHEMA = {
    "type": "object",
    "properties": {
        "actions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "theme": {"type": "string"},
                    "action_text": {"type": "string"},
                    "rationale": {"type": "string"},
                },
                "required": ["theme", "action_text", "rationale"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["actions"],
    "additionalProperties": False,
}


def _worth_flagging(trend: dict, top_n: int = 5) -> list[dict]:
    """Which themes actually warrant a recommended action: rising/new, or
    already urgent/negative even if flat — not just anything that showed up
    this period. Pure heuristic, no LLM call."""
    urgency_by_theme = {t["theme"]: t for t in trend["current"]["theme_urgency_ranking"]}
    candidates = []
    for d in trend["theme_deltas"]:
        if d["current_count"] == 0:
            continue
        info = urgency_by_theme.get(d["theme"], {})
        avg_urgency = info.get("avg_urgency_score", 0.0)
        avg_sentiment = info.get("avg_sentiment_score", 0.0)
        if d["direction"] in ("new", "up") or avg_urgency >= 0.5 or avg_sentiment < -0.3:
            candidates.append({**d, "avg_urgency_score": avg_urgency, "avg_sentiment_score": avg_sentiment})
    candidates.sort(key=lambda c: (c["avg_urgency_score"], c["current_count"]), reverse=True)
    return candidates[:top_n]


def _format_candidate(c: dict) -> str:
    delta = "n/a (new theme)" if c["delta_pct"] is None else f"{c['delta_pct']:+.1f}%"
    return (
        f'Theme "{c["theme"]}", current_count={c["current_count"]}, direction={c["direction"]}, '
        f"delta_pct={delta}, avg_urgency_score={c['avg_urgency_score']:.2f}, "
        f"avg_sentiment_score={c['avg_sentiment_score']:.2f}"
    )


def recommend_actions(trend: dict) -> list[dict]:
    """Recommend actions for whatever trend.py's compute_trend() output
    flags as worth attention. Returns [] when nothing qualifies (a genuinely
    calm period) or when AI analysis isn't available — never raises."""
    candidates = _worth_flagging(trend)
    if not candidates:
        return []

    providers = llm.available_providers()
    if not providers:
        return []

    message = "\n".join(_format_candidate(c) for c in candidates)
    provider = providers[0]
    client = llm.get_client(provider)
    try:
        if provider == "anthropic":
            response = llm.call_anthropic(client, message, SYSTEM_PROMPT, ACTIONS_SCHEMA, repair=False)
            if response.stop_reason == "refusal":
                return []
            text = next((b.text for b in response.content if b.type == "text"), "")
        else:
            call = llm.call_openai if provider == "openai" else llm.call_groq
            response = call(client, message, SYSTEM_PROMPT, ACTIONS_SCHEMA, repair=False)
            if response.choices[0].finish_reason == "content_filter":
                return []
            text = response.choices[0].message.content or ""

        data = llm.extract_json(text)
        if data is None:
            return []
        result = RecommendedActionsResult.model_validate(data)
        return [a.model_dump() for a in result.actions]
    except Exception:
        return []
