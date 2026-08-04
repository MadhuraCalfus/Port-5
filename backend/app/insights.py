"""Pure aggregation over feedback_items for the PM dashboard — category
frequency, sentiment distribution, urgency ranking, and period-over-period
trend deltas, bucketed into daily/weekly/monthly/yearly periods. No LLM
calls here: this is arithmetic over what feedback_ai already produced at
ingestion time. Turning these numbers into a recommended action or a
plain-language narrative happens in actions_ai.py / narrative_ai.py — this
module only answers "what happened" and "what changed," not "what should we
do about it."
"""
from collections import Counter
from datetime import datetime, timedelta, timezone

from . import store

PERIOD_TYPES = ("daily", "weekly", "monthly", "yearly")


def _period_key(created_at: str, period_type: str) -> str:
    dt = datetime.fromisoformat(created_at)
    if period_type == "daily":
        return dt.strftime("%Y-%m-%d")
    if period_type == "weekly":
        iso_year, iso_week, _ = dt.isocalendar()
        return f"{iso_year}-W{iso_week:02d}"
    if period_type == "monthly":
        return dt.strftime("%Y-%m")
    if period_type == "yearly":
        return dt.strftime("%Y")
    raise ValueError(f"period_type must be one of {PERIOD_TYPES}, got {period_type!r}")


def _period_bounds(period_type: str, period_key: str) -> tuple[str, str]:
    """The calendar start/end date (inclusive) a period key covers — used to
    label a period for a human ("Jul 14 - Jul 20, 2026") and, later, to
    persist period_start/period_end on a generated report."""
    if period_type == "daily":
        start = datetime.strptime(period_key, "%Y-%m-%d")
        end = start
    elif period_type == "weekly":
        iso_year, iso_week = period_key.split("-W")
        start = datetime.fromisocalendar(int(iso_year), int(iso_week), 1)  # Monday
        end = datetime.fromisocalendar(int(iso_year), int(iso_week), 7)  # Sunday
    elif period_type == "monthly":
        start = datetime.strptime(period_key + "-01", "%Y-%m-%d")
        next_month = start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(month=start.month + 1)
        end = next_month - timedelta(days=1)
    elif period_type == "yearly":
        start = datetime(int(period_key), 1, 1)
        end = datetime(int(period_key), 12, 31)
    else:
        raise ValueError(f"period_type must be one of {PERIOD_TYPES}, got {period_type!r}")
    return start.date().isoformat(), end.date().isoformat()


def current_period_key(period_type: str, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    return _period_key(now.isoformat(), period_type)


def _previous_period_key(period_type: str, period_key: str) -> str:
    """The immediately preceding period of the same type — handles
    month-length variance correctly by shifting from the period's start
    date (always the 1st for monthly) rather than a fixed day count."""
    start, _ = _period_bounds(period_type, period_key)
    start_dt = datetime.strptime(start, "%Y-%m-%d")
    if period_type == "daily":
        shifted = start_dt - timedelta(days=1)
    elif period_type == "weekly":
        shifted = start_dt - timedelta(days=7)
    elif period_type == "monthly":
        shifted = start_dt - timedelta(days=1)  # last day of the previous month
    elif period_type == "yearly":
        shifted = start_dt.replace(year=start_dt.year - 1)
    else:
        raise ValueError(f"period_type must be one of {PERIOD_TYPES}, got {period_type!r}")
    return _period_key(shifted.isoformat(), period_type)


def _group_by_period(rows: list[dict], period_type: str) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for r in rows:
        if not r.get("created_at"):
            continue
        grouped.setdefault(_period_key(r["created_at"], period_type), []).append(r)
    return grouped


def _category_frequency(rows: list[dict]) -> dict[str, int]:
    return dict(Counter(r["category"] for r in rows if r.get("category")))


def _sentiment_distribution(rows: list[dict]) -> dict[str, int]:
    return dict(Counter(r["sentiment_label"] for r in rows if r.get("sentiment_label")))


def _rating_distribution(rows: list[dict]) -> dict[int, int]:
    """Star-rating counts (1-5) from surveys only — tickets/reviews never
    carry a rating. Keyed by int, not the string keys everything else here
    uses, since a rating is a genuine 1-5 scale, not a category label."""
    return dict(Counter(r["rating"] for r in rows if r.get("rating") is not None))


def _category_urgency_ranking(rows: list[dict], top_n: int = 25, top_n_themes: int = 8) -> list[dict]:
    """Categories ranked by how urgently they need attention (avg urgency,
    then volume as a tiebreaker) — distinct from category_frequency, which
    just ranks by how often a category comes up regardless of severity.
    Includes the same customer_impact tier get_category_snapshot computes,
    so the Analytics page's per-category table doesn't need to re-derive it
    client-side. sentiment_counts answers "which category has more negative
    vs. positive feedback" directly, rather than just an averaged score;
    avg_rating/rated_count are None/0 for categories with no survey-sourced
    items — most categories come from tickets/reviews, which never carry a
    star rating. Each entry also carries its own theme breakdown ("themes")
    so a caller (Analytics' category picker) can show any category's
    themes, not just the single top one _top_category_with_themes defaults to."""
    by_category: dict[str, list[dict]] = {}
    for r in rows:
        if r.get("category"):
            by_category.setdefault(r["category"], []).append(r)

    ranked = []
    for category, items in by_category.items():
        avg_urgency = sum(i["urgency_score"] for i in items) / len(items)
        rated = [i["rating"] for i in items if i.get("rating") is not None]
        theme_counts = Counter(i["theme"] for i in items if i.get("theme"))
        ranked.append({
            "category": category,
            "count": len(items),
            "avg_urgency_score": round(avg_urgency, 2),
            "avg_sentiment_score": round(sum(i["sentiment_score"] for i in items) / len(items), 2),
            "sentiment_counts": dict(Counter(i["sentiment_label"] for i in items if i.get("sentiment_label"))),
            "avg_rating": round(sum(rated) / len(rated), 2) if rated else None,
            "rated_count": len(rated),
            "customer_impact": _customer_impact_tier(len(items), avg_urgency),
            "themes": [{"theme": t, "count": c} for t, c in theme_counts.most_common(top_n_themes)],
        })
    ranked.sort(key=lambda t: (t["avg_urgency_score"], t["count"]), reverse=True)
    return ranked[:top_n]


def _top_category_with_themes(category_frequency: dict[str, int], category_ranking: list[dict]) -> dict | None:
    """The single most-mentioned category (by raw volume — distinct from
    category_ranking's own urgency-first sort) plus its theme breakdown,
    looked up from the already-computed ranking rather than a second pass
    over the raw rows. Backs Analytics' "top category" card and is the
    *default* selection for its themes chart, which a PM can override to
    any other category via category_ranking's own per-entry "themes" field."""
    if not category_frequency:
        return None
    top_category, top_count = Counter(category_frequency).most_common(1)[0]
    entry = next((c for c in category_ranking if c["category"] == top_category), None)
    return {"category": top_category, "count": top_count, "themes": entry["themes"] if entry else []}


def _aggregate_insights(period_rows: list[dict], start: str, end: str) -> dict:
    """The aggregate shape shared by compute_period_insights (a fixed
    period bucket) and compute_range_insights (an arbitrary custom date
    range) — total volume, sentiment/urgency averages, category+theme
    breakdowns, and rating stats for one already-filtered set of rows."""
    rated_rows = [r for r in period_rows if r.get("rating") is not None]
    category_frequency = _category_frequency(period_rows)
    category_ranking = _category_urgency_ranking(period_rows)

    return {
        "period_start": start,
        "period_end": end,
        "total_items": len(period_rows),
        "actionable_count": sum(1 for r in period_rows if r.get("is_actionable_ticket")),
        "source_breakdown": dict(Counter(r["source_type"] for r in period_rows)),
        "sentiment_distribution": _sentiment_distribution(period_rows),
        "avg_sentiment_score": round(sum(r["sentiment_score"] for r in period_rows) / len(period_rows), 2) if period_rows else 0.0,
        "avg_urgency_score": round(sum(r["urgency_score"] for r in period_rows) / len(period_rows), 2) if period_rows else 0.0,
        "category_frequency": category_frequency,
        "category_urgency_ranking": category_ranking,
        "top_category": _top_category_with_themes(category_frequency, category_ranking),
        "rating_distribution": _rating_distribution(period_rows),
        "avg_rating": round(sum(r["rating"] for r in rated_rows) / len(rated_rows), 2) if rated_rows else None,
        "rated_count": len(rated_rows),
    }


def compute_period_insights(period_type: str, period_key: str | None = None, _rows: list[dict] | None = None) -> dict:
    """Aggregate stats for one period bucket. Defaults to the current
    period (today/this week/this month/this year) when period_key is
    omitted; pass an explicit key (e.g. "2026-W29") to look at a past one —
    available_periods lists every key that actually has data, so a caller
    can discover valid keys rather than guessing the format.

    _rows lets a caller that needs several period buckets from the same
    underlying data (compute_trend, compute_sentiment_series) pass in one
    already-fetched feedback_items list instead of each call re-fetching
    the whole table over the network — a callers-only optimization, not
    part of the public contract, hence the underscore."""
    if period_type not in PERIOD_TYPES:
        raise ValueError(f"period_type must be one of {PERIOD_TYPES}, got {period_type!r}")

    rows = _rows if _rows is not None else store.list_feedback_items(limit=100000)
    grouped = _group_by_period(rows, period_type)
    key = period_key or current_period_key(period_type)
    period_rows = grouped.get(key, [])
    start, end = _period_bounds(period_type, key)

    result = _aggregate_insights(period_rows, start, end)
    result["period_type"] = period_type
    result["period_key"] = key
    result["available_periods"] = sorted(grouped.keys(), reverse=True)
    return result


def compute_range_insights(start: str, end: str, _rows: list[dict] | None = None) -> dict:
    """Same aggregate shape as compute_period_insights, but for an
    arbitrary [start, end] date range (inclusive, both YYYY-MM-DD) instead
    of a fixed period bucket — backs Analytics' custom date-range picker.
    There's no "previous range" concept for an arbitrary window, so this
    has no trend/delta counterpart the way compute_trend provides for
    period buckets."""
    rows = _rows if _rows is not None else store.list_feedback_items(limit=100000)
    end_exclusive = (datetime.strptime(end, "%Y-%m-%d") + timedelta(days=1)).date().isoformat()
    range_rows = [r for r in rows if r.get("created_at") and start <= r["created_at"][:10] < end_exclusive]
    return _aggregate_insights(range_rows, start, end)


def compute_trend(period_type: str, period_key: str | None = None, _rows: list[dict] | None = None) -> dict:
    """Period-over-period change per category — the up/down deltas a PM sees
    on the trends tab. A category with 0 occurrences last period and >0 this
    period is "new" (a % change isn't meaningful); the reverse is "resolved".

    _rows lets a caller that already fetched feedback_items (e.g.
    get_category_snapshot, which needs its own pass over the same rows right
    after this) pass it in instead of this function re-fetching over the
    network — same callers-only optimization as compute_period_insights'
    _rows param."""
    rows = _rows if _rows is not None else store.list_feedback_items(limit=100000)
    current = compute_period_insights(period_type, period_key, _rows=rows)
    prev_key = _previous_period_key(period_type, current["period_key"])
    previous = compute_period_insights(period_type, prev_key, _rows=rows)

    category_deltas = []
    for category in set(current["category_frequency"]) | set(previous["category_frequency"]):
        cur_count = current["category_frequency"].get(category, 0)
        prev_count = previous["category_frequency"].get(category, 0)
        if prev_count == 0:
            direction, delta_pct = "new", None
        elif cur_count == 0:
            direction, delta_pct = "resolved", -100.0
        else:
            delta_pct = round(100 * (cur_count - prev_count) / prev_count, 1)
            direction = "up" if delta_pct > 0 else "down" if delta_pct < 0 else "flat"
        category_deltas.append({
            "category": category,
            "current_count": cur_count,
            "previous_count": prev_count,
            "delta_pct": delta_pct,
            "direction": direction,
        })
    # "new" categories (delta_pct=None) surface first — an unseen-before
    # category is at least as noteworthy as a large percentage swing on an
    # existing one.
    category_deltas.sort(key=lambda d: (d["delta_pct"] is None, d["delta_pct"] or 0, d["current_count"]), reverse=True)

    return {
        "period_type": period_type,
        "current_period_key": current["period_key"],
        "previous_period_key": prev_key,
        "current_period_start": current["period_start"],
        "current_period_end": current["period_end"],
        "avg_sentiment_score_delta": round(current["avg_sentiment_score"] - previous["avg_sentiment_score"], 2),
        "avg_urgency_score_delta": round(current["avg_urgency_score"] - previous["avg_urgency_score"], 2),
        "total_items_delta": current["total_items"] - previous["total_items"],
        "category_deltas": category_deltas,
        "current": current,
        "previous": previous,
    }


def get_period_items(period_type: str, period_key: str | None = None) -> list[dict]:
    """Every feedback_items row in one period, in full — the raw data behind
    compute_period_insights' aggregates, used for the PM's PDF/CSV export so
    a report contains every underlying feedback/survey item, not just the
    summary numbers."""
    key = period_key or current_period_key(period_type)
    start, end = _period_bounds(period_type, key)
    end_exclusive = (datetime.strptime(end, "%Y-%m-%d") + timedelta(days=1)).date().isoformat()
    return store.list_feedback_items_between(start, end_exclusive)


def compute_sentiment_series(period_type: str, num_periods: int = 8, end_period_key: str | None = None) -> list[dict]:
    """The num_periods periods ending at end_period_key (defaults to the
    current period), oldest first — the data behind the "over time" charts.
    Passing an explicit end_period_key lets a PM browsing a past week/month/
    year still see a trend line anchored on what they're looking at, rather
    than always trailing up to today regardless of the period selected
    elsewhere on the page."""
    key = end_period_key or current_period_key(period_type)
    keys = [key]
    for _ in range(num_periods - 1):
        key = _previous_period_key(period_type, key)
        keys.append(key)
    keys.reverse()

    rows = store.list_feedback_items(limit=100000)
    series = []
    for k in keys:
        stats = compute_period_insights(period_type, k, _rows=rows)
        series.append({
            "period_key": k,
            "period_start": stats["period_start"],
            "period_end": stats["period_end"],
            "avg_sentiment_score": stats["avg_sentiment_score"],
            "avg_urgency_score": stats["avg_urgency_score"],
            "total_items": stats["total_items"],
            "avg_rating": stats["avg_rating"],
            "rated_count": stats["rated_count"],
        })
    return series


def _customer_impact_tier(count: int, avg_urgency: float) -> str:
    """A simple, deliberately non-LLM heuristic — how many customers plus
    how severe, collapsed into one label a PM can scan at a glance. Distinct
    from urgency alone: a category with only 1 mention can't be "High
    impact" no matter how urgent that one report is."""
    if (count >= 5 and avg_urgency >= 0.34) or avg_urgency >= 0.75:
        return "High"
    if count >= 2 or avg_urgency >= 0.34:
        return "Medium"
    return "Low"


