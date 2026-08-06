"""Nykaa Pulse's own ticket analytics — the same status/priority/category/
team/tone breakdowns + timeline `AnalyticsTab.jsx` already computes for the
shared tickets table, mirrored here over np_tickets. There's no "manual
routing time" baseline for Nykaa Pulse tickets (nothing was ever hand-routed
here), so the AI-vs-manual time-saved economics from analytics.py's
compute_analytics() don't have a meaningful analog and aren't reproduced.
"""
from collections import Counter

from . import nykaa_store as npstore
from .insights import _period_bounds


def _bucket(rows: list[dict], field: str) -> dict[str, int]:
    return dict(Counter(r[field] for r in rows if r.get(field) is not None))


def _timeline(rows: list[dict]) -> list[dict]:
    counts = Counter(r["created_at"][:10] for r in rows if r.get("created_at"))
    return [{"date": date, "count": counts[date]} for date in sorted(counts)]


def _within_period(rows: list[dict], period_type: str | None, period_key: str | None, date_field: str = "created_at") -> list[dict]:
    """Both None (the default) means all-time, same convention as
    analytics.py's own _within_period."""
    if not period_type or not period_key:
        return rows
    start, end = _period_bounds(period_type, period_key)
    return [r for r in rows if r.get(date_field) and str(r[date_field])[:10] >= start and str(r[date_field])[:10] <= end]


def compute_ticket_analytics(period_type: str | None = None, period_key: str | None = None) -> dict:
    rows = _within_period(npstore.list_all_np_tickets(), period_type, period_key)
    # AI-resolved chats key their timestamp as started_at rather than
    # created_at (grouped-conversation summary, not a single row insert).
    self_resolved_rows = _within_period(npstore.list_ai_resolved_chats(), period_type, period_key, date_field="started_at")
    total = len(rows)
    self_resolved_count = len(self_resolved_rows)

    if total == 0 and self_resolved_count == 0:
        return {
            "total_tickets": 0,
            "self_resolved_count": 0,
            "deflection_rate_pct": 0,
            "category_breakdown": {},
            "priority_breakdown": {},
            "team_breakdown": {},
            "tone_breakdown": {},
            "status_breakdown": {},
            "timeline": [],
        }

    return {
        "total_tickets": total,
        "self_resolved_count": self_resolved_count,
        "deflection_rate_pct": round(100 * self_resolved_count / (self_resolved_count + total), 1) if (self_resolved_count + total) else 0,
        "category_breakdown": _bucket(rows, "category"),
        "priority_breakdown": _bucket(rows, "priority"),
        "team_breakdown": _bucket(rows, "team"),
        "tone_breakdown": _bucket(rows, "tone"),
        "status_breakdown": dict(Counter(r["status"] for r in rows)),
        "timeline": _timeline(rows),
    }
