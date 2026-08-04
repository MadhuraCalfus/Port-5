"""AI-recommended actions for categories that are worsening or already
urgent — the last step in insights.py's trend computation. This module
never reads raw customer text: it takes the aggregated numbers insights.py
already computed (category, count, trend direction/%, avg urgency, avg
sentiment) and asks the model what a product/CX team should actually do
about them.

Which categories are "worth flagging" is decided here with plain arithmetic
(worth_flagging), not by the model — the model's only job is writing a
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
feedback categories. You are given a short list of categories that are worsening or already urgent — \
rising in volume, negative in sentiment, or high urgency — each with its current count, trend direction \
and percent change, average sentiment score, and average urgency score. You are NOT given the raw \
customer text, only these aggregated numbers — do not invent specifics you weren't given.

Rules:
- Recommend at most one action per category you're given — never invent a category not in the list, and \
never skip a category you were given without at least a light-touch action.
- action_text MUST name the exact category you were given, by its exact name, somewhere in the sentence \
(e.g. "...for the Delivery & Logistics reports..." or "...regarding Product Quality & Fit issues..."). This is \
shown as a flat, unlabeled list with no category badge or grouping next to it, so the category name is \
the ONLY way a reader knows which issue this is about — NEVER write only "this theme," "this issue," or \
"this new theme" without also stating what it is by name at least once in the same sentence.
- action_text must be a concrete, specific action a product or CX team could actually start this \
week — e.g. "Escalate the Delivery & Logistics reports about late couriers to the Order & Delivery Team as a \
priority and have CX post a status update to affected customers." — never vague filler like "look into \
this" or "investigate further." It must NEVER cite raw internal numbers either (no "sentiment 0.70", no \
"urgency 0.38", no "+300%") — it describes the action itself, not the data behind it.
- rationale explains WHY in plain, everyday language a non-technical manager would understand at a \
glance — how many customers seem affected, whether it's getting better or worse, and how upset people \
sound. NEVER cite the raw internal numbers you were given (no "urgency score 0.75", no "-0.6 sentiment", \
no "+180%") — translate them into words instead (e.g. "a small but growing number of customers," \
"people sound genuinely frustrated," "this has more than doubled since last period," "only one or two \
reports so far"). Still be specific about scale and direction, just never in raw score form.
- Match the intensity of the action to the severity of the data: a category with low urgency and only \
mildly negative sentiment gets a lightweight action (monitor, note for next release), not an escalation \
— don't over-escalate everything you're handed just because it made the list.

Worked examples, for calibration — one high-severity and one low-severity, to show the range of \
appropriate intensity, and how the category name is always spelled out by name rather than left as "this \
theme":
1. Category "Delivery & Logistics", current_count=14, direction=up, delta_pct=180.0, avg_urgency_score=0.75, \
avg_sentiment_score=-0.6 -> action_text="Escalate the Delivery & Logistics reports about late couriers to \
the Order & Delivery Team as a priority and have CX post a status update to affected customers.", \
rationale="Complaints about this have nearly tripled since last period, and customers sound genuinely \
frustrated — this is actively getting worse, not just a one-off."
2. Category "Review & App Flow Friction", current_count=3, direction=flat, delta_pct=0.0, avg_urgency_score=0.2, \
avg_sentiment_score=-0.3 -> action_text="Log the Review & App Flow Friction items for the next regular \
release cycle — no immediate escalation needed.", rationale="Only a handful of customers have mentioned \
this and the number hasn't grown — worth keeping on the list, but nothing urgent right now.\""""

ACTIONS_SCHEMA = {
    "type": "object",
    "properties": {
        "actions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "action_text": {"type": "string"},
                    "rationale": {"type": "string"},
                },
                "required": ["category", "action_text", "rationale"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["actions"],
    "additionalProperties": False,
}


def worth_flagging(trend: dict, top_n: int = 5) -> list[dict]:
    """Which categories actually warrant a recommended action: rising/new,
    or already urgent/negative even if flat — not just anything that showed
    up this period. Pure heuristic, no LLM call."""
    urgency_by_category = {t["category"]: t for t in trend["current"]["category_urgency_ranking"]}
    candidates = []
    for d in trend["category_deltas"]:
        if d["current_count"] == 0:
            continue
        info = urgency_by_category.get(d["category"], {})
        avg_urgency = info.get("avg_urgency_score", 0.0)
        avg_sentiment = info.get("avg_sentiment_score", 0.0)
        if d["direction"] in ("new", "up") or avg_urgency >= 0.5 or avg_sentiment < -0.3:
            candidates.append({**d, "avg_urgency_score": avg_urgency, "avg_sentiment_score": avg_sentiment})
    candidates.sort(key=lambda c: (c["avg_urgency_score"], c["current_count"]), reverse=True)
    return candidates[:top_n]


def _format_candidate(c: dict) -> str:
    delta = "n/a (new category)" if c["delta_pct"] is None else f"{c['delta_pct']:+.1f}%"
    return (
        f'Category "{c["category"]}", current_count={c["current_count"]}, direction={c["direction"]}, '
        f"delta_pct={delta}, avg_urgency_score={c['avg_urgency_score']:.2f}, "
        f"avg_sentiment_score={c['avg_sentiment_score']:.2f}"
    )


def generate_action_texts(candidates: list[dict]) -> list[dict]:
    """The LLM call shared by every caller that already has its own
    candidate list — deciding WHO qualifies is the caller's job (worth_
    flagging for the period-level recommended-actions flow; a different,
    negative-feedback-specific criterion for the Category Insights tab); this
    function's only job is writing a good action for candidates it's
    handed. Each candidate needs category/current_count/direction/delta_pct/
    avg_urgency_score/avg_sentiment_score (see _format_candidate). Returns
    [] when there's nothing to do or AI analysis isn't available — never
    raises."""
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


def recommend_actions(trend: dict) -> list[dict]:
    """Recommend actions for whatever trend.py's compute_trend() output
    flags as worth attention (see worth_flagging) — the period-level
    Reports & Actions tab's recommendations. Returns [] when nothing
    qualifies (a genuinely calm period) or when AI analysis isn't
    available — never raises."""
    return generate_action_texts(worth_flagging(trend))
