"""Pure aggregation over feedback_items for the PM dashboard — theme
frequency, sentiment distribution, and urgency ranking, bucketed into
daily/weekly/monthly/yearly periods. No LLM calls here: this is arithmetic
over what feedback_ai already produced at ingestion time. The narrative
summary and period-over-period trend deltas built on top of this live in
later modules (insights_trends.py / weekly_summary.py) — this module only
answers "what happened in this period," not "what changed" or "what should
we do about it."
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



def _group_by_period(rows: list[dict], period_type: str) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for r in rows:
        if not r.get("created_at"):
            continue
        grouped.setdefault(_period_key(r["created_at"], period_type), []).append(r)
    return grouped


def _theme_frequency(rows: list[dict]) -> dict[str, int]:
    return dict(Counter(r["theme"] for r in rows if r.get("theme")))


def _sentiment_distribution(rows: list[dict]) -> dict[str, int]:
    return dict(Counter(r["sentiment_label"] for r in rows if r.get("sentiment_label")))


def _theme_urgency_ranking(rows: list[dict], top_n: int = 10) -> list[dict]:
    """Themes ranked by how urgently they need attention (avg urgency, then
    volume as a tiebreaker) — distinct from theme_frequency, which just
    ranks by how often a theme comes up regardless of severity."""
    by_theme: dict[str, list[dict]] = {}
    for r in rows:
        if r.get("theme"):
            by_theme.setdefault(r["theme"], []).append(r)

    ranked = [
        {
            "theme": theme,
            "count": len(items),
            "avg_urgency_score": round(sum(i["urgency_score"] for i in items) / len(items), 2),
            "avg_sentiment_score": round(sum(i["sentiment_score"] for i in items) / len(items), 2),
        }
        for theme, items in by_theme.items()
    ]
    ranked.sort(key=lambda t: (t["avg_urgency_score"], t["count"]), reverse=True)
    return ranked[:top_n]


def compute_period_insights(period_type: str, period_key: str | None = None) -> dict:
    """Aggregate stats for one period bucket. Defaults to the current
    period (today/this week/this month/this year) when period_key is
    omitted; pass an explicit key (e.g. "2026-W29") to look at a past one —
    available_periods lists every key that actually has data, so a caller
    can discover valid keys rather than guessing the format."""
    if period_type not in PERIOD_TYPES:
        raise ValueError(f"period_type must be one of {PERIOD_TYPES}, got {period_type!r}")

    rows = store.list_feedback_items(limit=100000)
    grouped = _group_by_period(rows, period_type)
    key = period_key or current_period_key(period_type)
    period_rows = grouped.get(key, [])
    start, end = _period_bounds(period_type, key)

    return {
        "period_type": period_type,
        "period_key": key,
        "period_start": start,
        "period_end": end,
        "total_items": len(period_rows),
        "actionable_count": sum(1 for r in period_rows if r.get("is_actionable_ticket")),
        "source_breakdown": dict(Counter(r["source_type"] for r in period_rows)),
        "sentiment_distribution": _sentiment_distribution(period_rows),
        "avg_sentiment_score": round(sum(r["sentiment_score"] for r in period_rows) / len(period_rows), 2) if period_rows else 0.0,
        "avg_urgency_score": round(sum(r["urgency_score"] for r in period_rows) / len(period_rows), 2) if period_rows else 0.0,
        "theme_frequency": _theme_frequency(period_rows),
        "theme_urgency_ranking": _theme_urgency_ranking(period_rows),
        "available_periods": sorted(grouped.keys(), reverse=True),
    }
