"""Aggregate stats over everything routed so far — powers the dashboard."""
from collections import Counter

from . import store
from .insights import _period_bounds


def _bucket(rows: list[dict], field: str) -> dict[str, int]:
    # Unrouted ("New") tickets have no category/priority/team/tone yet —
    # exclude them rather than let them show up as a spurious null bucket.
    return dict(Counter(r[field] for r in rows if r.get(field) is not None))


def _timeline(rows: list[dict]) -> list[dict]:
    """Ticket volume per calendar day (UTC date from created_at), oldest
    first — every ticket has a created_at regardless of routing status, so
    this counts everything, not just routed tickets."""
    counts = Counter(r["created_at"][:10] for r in rows if r.get("created_at"))
    return [{"date": date, "count": counts[date]} for date in sorted(counts)]


def _within_period(rows: list[dict], period_type: str | None, period_key: str | None) -> list[dict]:
    """Both None (the default) means all-time, unchanged from before this
    filter existed — a period is only applied when the Admin dashboard's
    Weekly/Monthly/Yearly toggle actually picks one."""
    if not period_type or not period_key:
        return rows
    start, end = _period_bounds(period_type, period_key)
    return [r for r in rows if r.get("created_at") and start <= r["created_at"][:10] <= end]


def compute_analytics(period_type: str | None = None, period_key: str | None = None) -> dict:
    rows = _within_period(store.list_tickets(limit=100000, offset=0), period_type, period_key)
    self_resolved_rows = _within_period(store.list_self_resolved(limit=100000, offset=0), period_type, period_key)
    total = len(rows)
    self_resolved_count = len(self_resolved_rows)

    if total == 0:
        return {
            "total_tickets": 0,
            "self_resolved_count": self_resolved_count,
            "deflection_rate_pct": 100.0 if self_resolved_count else 0,
            "avg_ai_latency_ms": 0,
            "avg_manual_seconds": store.ASSUMED_MANUAL_SECONDS,
            "measured_manual_count": 0,
            "total_ai_seconds": 0,
            "total_manual_seconds": 0,
            "total_time_saved_seconds": 0,
            "time_saved_pct": 0,
            "category_breakdown": {},
            "priority_breakdown": {},
            "team_breakdown": {},
            "tone_breakdown": {},
            "mode_breakdown": {},
            "status_breakdown": {},
            "timeline": [],
            "ambiguous_count": 0,
            "escalated_count": 0,
            "feedback_count": 0,
            "agreement_rate": None,
        }

    # A ticket only has latency_ms (and everything else AI-derived) once it's
    # actually been classified — "New" tickets sitting unconfirmed in the
    # queue have neither, so the AI-vs-manual timing math only makes sense
    # over the ones AI has actually touched.
    classified = [r for r in rows if r.get("latency_ms") is not None]
    classified_count = len(classified)

    total_ai_seconds = sum(r["latency_ms"] for r in classified) / 1000.0
    measured = [r["manual_time_seconds"] for r in classified if r.get("manual_time_seconds") is not None]
    total_manual_seconds = sum(measured) + (classified_count - len(measured)) * store.ASSUMED_MANUAL_SECONDS

    reviewed = [r for r in rows if r.get("reviewed")]
    corrected = [
        r for r in reviewed
        if r.get("corrected_category") is not None or r.get("corrected_priority") is not None or r.get("corrected_team") is not None
    ]

    return {
        "total_tickets": total,
        # Out of every interaction that started with "describe an issue" —
        # self-resolved by AI, or an actual ticket — the share AI closed out
        # on its own before a human or team was ever involved.
        "self_resolved_count": self_resolved_count,
        "deflection_rate_pct": round(100 * self_resolved_count / (self_resolved_count + total), 1),
        "avg_ai_latency_ms": round(sum(r["latency_ms"] for r in classified) / classified_count, 1) if classified_count else 0,
        "avg_manual_seconds": round(total_manual_seconds / classified_count, 1) if classified_count else store.ASSUMED_MANUAL_SECONDS,
        "measured_manual_count": len(measured),
        "total_ai_seconds": round(total_ai_seconds, 2),
        "total_manual_seconds": round(total_manual_seconds, 2),
        "total_time_saved_seconds": round(total_manual_seconds - total_ai_seconds, 2),
        "time_saved_pct": round(100 * (total_manual_seconds - total_ai_seconds) / total_manual_seconds, 1) if total_manual_seconds else 0,
        "category_breakdown": _bucket(rows, "category"),
        "priority_breakdown": _bucket(rows, "priority"),
        "team_breakdown": _bucket(rows, "team"),
        "tone_breakdown": _bucket(rows, "tone"),
        "mode_breakdown": _bucket(rows, "mode"),
        # Unlike the breakdowns above, status is never null (every ticket
        # defaults to "New"), so New tickets show up here even though they
        # have no category/priority/team/tone yet.
        "status_breakdown": dict(Counter(r["status"] for r in rows)),
        "timeline": _timeline(rows),
        "ambiguous_count": sum(1 for r in rows if r["is_ambiguous"]),
        "escalated_count": sum(1 for r in rows if r["escalated"]),
        "feedback_count": len(reviewed),
        "agreement_rate": None if not reviewed else round(100 * (1 - len(corrected) / len(reviewed)), 1),
    }


def compute_team_summary() -> dict:
    """Per-team workload: how many of that team's tickets are assigned
    (just routed, not started), in progress, or resolved. Every team that
    actually exists in this deployment shows up even with zero tickets, so
    an empty team is visibly empty rather than just missing."""
    rows = store.list_tickets(limit=100000, offset=0)
    counts = {team: {"assigned": 0, "in_progress": 0, "resolved": 0} for team in store.list_known_teams()}

    for r in rows:
        team = r.get("team")
        if team not in counts:
            continue
        if r["status"] == "Routed":
            counts[team]["assigned"] += 1
        elif r["status"] == "In Progress":
            counts[team]["in_progress"] += 1
        elif r["status"] == "Resolved":
            counts[team]["resolved"] += 1

    return {
        "teams": [
            {"team": team, **c, "total": c["assigned"] + c["in_progress"] + c["resolved"]}
            for team, c in counts.items()
        ]
    }
