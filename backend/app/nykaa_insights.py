"""Nykaa Pulse — catalog-aware analytics for the PM dashboard (Phase 3).

The teardown's own PM-analytics gap list is the brief here: Nykaa's metrics
pyramid "stops at aggregate counts" and needs brand/category granularity,
drop-off-step visibility, and sentiment depth to be actionable. Rather than
duplicating insights.py's period-bucketing/trend-delta/urgency-ranking logic
or narrative_ai.py's report-writing prompt, this module reuses both
unchanged: insights.compute_trend and narrative_ai.generate_report both
accept a plain list of feedback_items-shaped dicts via their `_rows`
parameter — so the only new work here is building rows in that exact shape
but with `category` relabeled to a catalog attribute (brand, or the
product's own catalog category) instead of feedback_ai's classification
category. Everything downstream — period math, category_deltas, urgency
ranking, the plain-language narrative — runs exactly as it already does for
"My Existing Project"'s Reports tab, just now answering "which brand" or
"which catalog category" instead of "which kind of problem."
"""
from . import insights, narrative_ai
from . import nykaa_store as npstore


def _relabel(rows: list[dict], catalog_field: str) -> list[dict]:
    """Copies each row with `category` overwritten by the requested catalog
    attribute — insights.py only ever reads the `category` key by name, so
    this is the entire bridge between feedback_ai's taxonomy and the
    catalog's own brand/category dimensions."""
    return [{**r, "category": r[catalog_field]} for r in rows if r.get(catalog_field)]


def compute_brand_trend(period_type: str, period_key: str | None = None) -> dict:
    rows = _relabel(npstore.list_review_feedback_with_catalog(), "brand")
    return insights.compute_trend(period_type, period_key, _rows=rows)


def compute_category_trend(period_type: str, period_key: str | None = None) -> dict:
    rows = _relabel(npstore.list_review_feedback_with_catalog(), "catalog_category")
    return insights.compute_trend(period_type, period_key, _rows=rows)


def generate_brand_report(period_type: str, period_key: str | None = None) -> dict:
    """The "weekly Nykaa-flavored narrative report" the plan calls for —
    same generate_report() the existing Reports & Actions tab already uses,
    fed brand-level trend data instead of feedback-category trend data, so
    it reads as a brand scorecard rather than a generic issue digest.

    Persisted per (period_type, resolved period_key) so viewing the same
    past period twice doesn't cost a second LLM call — a concluded period's
    data can't change, so its report is generated once and reread after.
    The *current*, still-accumulating period is the one exception: it's
    always regenerated fresh (today's date decides which key counts as
    current), and the fresh result overwrites its own cache entry so that
    once the period ends, whatever was last generated is already sitting
    there ready — no separate "did anyone view this after it closed" step
    needed."""
    key = period_key or insights.current_period_key(period_type)
    is_current = key == insights.current_period_key(period_type)
    if not is_current:
        cached = npstore.get_np_periodic_report(period_type, key)
        if cached:
            return cached

    trend = compute_brand_trend(period_type, key)
    report, mode, model_used = narrative_ai.generate_report(trend)
    result = {"report": report, "mode": mode, "model_used": model_used, "trend": trend}
    npstore.upsert_np_periodic_report(period_type, key, result)
    return result


def overview() -> dict:
    """Headline numbers for the PM's Nykaa Pulse Overview sub-tab: order
    volume + GMV, delivery satisfaction, review conversion, time-to-
    moderation, and photo-attach rate — the order/catalog-level metrics
    insights.py has no visibility into, alongside a quick sentiment read
    over Nykaa Pulse reviews specifically (not the whole app's feedback)."""
    catalog = npstore.compute_catalog_overview()
    funnel = npstore.compute_order_funnel()
    review_rows = npstore.list_review_feedback_with_catalog()

    total = funnel["total_items"] or 0
    sentiment_counts = {"positive": 0, "neutral": 0, "negative": 0}
    for r in review_rows:
        if r.get("sentiment_label") in sentiment_counts:
            sentiment_counts[r["sentiment_label"]] += 1

    return {
        **catalog,
        "funnel": {
            "orders_placed": funnel["total_items"],
            "reviewed": funnel["reviewed_items"],
            "review_rate_pct": round(100 * funnel["reviewed_items"] / total, 1) if total else 0.0,
            "with_photo": funnel["items_with_photo"],
            "photo_attach_rate_pct": round(100 * funnel["items_with_photo"] / total, 1) if total else 0.0,
            "published": funnel["published_items"],
        },
        "review_sentiment": sentiment_counts,
        "review_count": len(review_rows),
    }


def brand_breakdown(period_type: str = "monthly", period_key: str | None = None) -> list[dict]:
    """Per-brand rating/sentiment/urgency ranking — reuses insights.py's
    category_urgency_ranking (via compute_period_insights) exactly as-is,
    just fed brand-relabeled rows."""
    rows = _relabel(npstore.list_review_feedback_with_catalog(), "brand")
    return insights.compute_period_insights(period_type, period_key, _rows=rows)["category_urgency_ranking"]


def category_breakdown(period_type: str = "monthly", period_key: str | None = None) -> list[dict]:
    rows = _relabel(npstore.list_review_feedback_with_catalog(), "catalog_category")
    return insights.compute_period_insights(period_type, period_key, _rows=rows)["category_urgency_ranking"]
