"""Chart shaping for the PM Analytics chatbot (nykaa_chat_sql.py).

Kept in its own file, separate from the question -> SQL -> rows pipeline:
this module only ever turns already-fetched rows into a small, generic
{type, points, x_label, y_label} spec the frontend can render directly. No
database or LLM calls happen here.
"""

MAX_CHART_POINTS = 20
CHART_TYPES = {"bar", "line", "pie"}


def build_chart_spec(chart_type: str | None, x_field: str | None, y_field: str | None, y_label: str | None, rows: list[dict]) -> dict | None:
    """rows are dicts straight from the executed SQL query. Returns None
    whenever there's nothing sensible to chart, so callers can just check
    truthiness rather than inspect points."""
    if chart_type not in CHART_TYPES or not rows or not x_field or not y_field:
        return None
    if x_field not in rows[0] or y_field not in rows[0]:
        return None

    points = []
    for row in rows:
        x, y = row.get(x_field), row.get(y_field)
        if x is None or y is None:
            continue
        try:
            y = float(y)
        except (TypeError, ValueError):
            continue
        points.append({"name": str(x), "value": y})
    if not points:
        return None

    if chart_type in ("bar", "pie"):
        points.sort(key=lambda p: p["value"], reverse=True)
    points = points[:MAX_CHART_POINTS]

    return {
        "type": chart_type,
        "points": points,
        "x_label": x_field.replace("_", " "),
        "y_label": (y_label or y_field).replace("_", " "),
    }
