"""PM Analytics chatbot — free-text question -> guardrailed SQL -> rows.

Same multi-provider LLM plumbing and try/repair/fallback shape as
classifier.py's _run_provider (see llm_providers.py), applied to a new kind
of output: a read-only SQL query instead of a ticket classification.

Scoped to feedback/reviews only — no ticket data is ever exposed here (see
ALLOWED_TABLES and the source_type = 'review' rule below).

Guardrails are two independent layers, both applied to every question:
1. App-level (_validate_sql): single statement, SELECT-only, table names
   restricted to an explicit whitelist, forced LIMIT.
2. DB-level (_run_readonly): the query executes inside a Postgres
   transaction explicitly set READ ONLY, then rolled back — so even a
   guardrail gap can't reach a write.

Chart shaping is deliberately NOT here — see nykaa_chat_chart.py.
"""
import json
import re
from contextlib import contextmanager
from datetime import datetime, timezone

from . import llm_providers as llm
from . import nykaa_chat_chart
from . import store

# ---- Guardrail: table whitelist ---------------------------------------
# Feedback/review + catalog tables only — no np_tickets, no ticket data of
# any kind. Also excludes users, np_beauty_profiles (personal skin/hair
# data), and np_chat_turns/np_ticket_comments (raw conversation text) even
# though they're also technically read-only-safe — this chatbot answers
# stats questions about feedback and reviews, not a general database browser.
ALLOWED_TABLES = {
    "np_feedback_items",
    "np_products",
    "np_brands",
    "np_categories",
    "np_subcategories",
    "np_sub_subcategories",
    "np_orders",
    "np_order_items",
}

# The exact join path, copied from nykaa_store.list_review_feedback_with_catalog
# — np_feedback_items has NO product_id column, and it also holds ticket-
# sourced rows (source_type='ticket') that must never surface here.
SCHEMA_DESCRIPTION = """Tables you may query (Postgres):

np_feedback_items — one row per customer review, already scored by an AI pipeline. ALWAYS add
  `WHERE source_type = 'review'` (or `AND source_type = 'review'`) — this table also contains
  ticket-sourced rows (source_type = 'ticket') which are OUT OF SCOPE and must never be included.
  Columns: source_ref (int — NOT a product id; it is np_order_items.id for review rows, see the
    join path below), rating (int, 1-5, nullable), sentiment_label (positive/neutral/negative),
    sentiment_score (real), category (text — review taxonomy: "Product Quality & Fit",
    "Packaging & Damage", "Delivery & Logistics", "Review & App Flow Friction",
    "Authenticity & Trust", "Personalization Mismatch", "Pricing & Offers", "Rewards & Loyalty",
    "Customer Support", "General Praise / Other"), theme (text, free-form short label),
    urgency_score (real, 0=no urgency to 1=needs immediate attention — in practice review scores
    top out around 0.6, since this is asynchronous feedback text rather than a live escalation, so
    treat urgency_score >= 0.5 as "critical"/"high urgency" when asked, not a higher number),
    is_actionable_ticket (0/1), created_at (text, ISO-8601 timestamp — this review's OWN
    timestamp; use this column, not np_orders.placed_at, whenever a question is about when a
    review/rating happened, e.g. "ratings in 2026", "reviews this week"). This is the ONLY date
    column reachable without joining np_orders — do not reach for placed_at/delivered_at unless
    the question is specifically about order or delivery timing.

np_order_items — id, order_id, product_id (-> np_products.id), quantity, unit_price_at_purchase,
  rating. This table has NO date/timestamp column of its own (no created_at, no placed_at) and NO
  direct link to np_products.brand_id/category_id — to reach a review's product/brand you MUST
  go through this table:
    np_feedback_items.source_ref = np_order_items.id AND np_feedback_items.source_type = 'review'
    np_order_items.product_id = np_products.id

np_products — id, category_id (-> np_categories.id), brand_id (-> np_brands.id),
  subcategory_id (-> np_subcategories.id), sub_subcategory_id (-> np_sub_subcategories.id), name,
  description, price_inr (numeric), created_at.
np_brands — id, name.
np_categories — id, name.
np_subcategories — id, category_id, name.
np_sub_subcategories — id, subcategory_id, name.
np_orders — id, user_id, status, placed_at, delivered_at, total_amount, delivery_rating (1-5),
  delivery_compliment. placed_at/delivered_at live ONLY here, reached via
  np_order_items.order_id = np_orders.id — never write oi.placed_at or f.placed_at, they don't
  exist. Only join np_orders in if the question is about order/delivery timing specifically.

Worked example — "how is brand X doing, by sentiment":
SELECT f.sentiment_label AS sentiment, COUNT(*) AS review_count
FROM np_feedback_items f
JOIN np_order_items oi ON oi.id = f.source_ref
JOIN np_products p ON p.id = oi.product_id
JOIN np_brands b ON b.id = p.brand_id
WHERE f.source_type = 'review' AND b.name ILIKE 'X'
GROUP BY f.sentiment_label
ORDER BY review_count DESC

Worked example — "line graph of ratings for brand X in 2026" (a review-timing question — note
np_orders is NOT needed here, since the rating and the date both live on np_feedback_items):
SELECT DATE_TRUNC('month', f.created_at::date) AS review_month, AVG(f.rating) AS avg_rating
FROM np_feedback_items f
JOIN np_order_items oi ON oi.id = f.source_ref
JOIN np_products p ON p.id = oi.product_id
JOIN np_brands b ON b.id = p.brand_id
WHERE f.source_type = 'review' AND b.name ILIKE 'X'
  AND f.created_at::date >= '2026-01-01' AND f.created_at::date <= '2026-12-31'
GROUP BY review_month
ORDER BY review_month"""


def _system_prompt(today_iso: str) -> str:
    return f"""You are a data analyst assistant for a beauty e-commerce PM dashboard. Given a \
product manager's plain-English question about customer feedback/reviews, write ONE read-only \
Postgres query that answers it, plus an optional chart suggestion.

First decide in_scope: true only if the question is genuinely about this app's customer \
feedback/reviews/ratings data (the tables below) — including follow-ups like "why" or "show me \
more" about a prior answer. Set in_scope=false for anything else: general knowledge questions \
("who is the president of India"), small talk, requests about unrelated topics, or requests to \
modify/delete data. When in_scope is false, set sql, x_field, y_field, and y_label to empty \
strings and chart_type to "none" — do not attempt to write a query for an out-of-scope question.

Today's date is {today_iso}. Resolve relative time expressions ("this week", "last 7 days", \
"this month") against that date using created_at/placed_at (cast with ::date or ::timestamp — \
they're stored as ISO-8601 text). Prefer `date_trunc('week', CURRENT_DATE)` / \
`date_trunc('month', CURRENT_DATE)` for period-start boundaries over EXTRACT-based arithmetic.

{SCHEMA_DESCRIPTION}

Strict rules (only apply once in_scope is true):
- Write exactly ONE statement. Plain SELECT only — no WITH/CTEs (use a subquery in FROM instead \
if you need one), and never INSERT/UPDATE/DELETE/DROP/ALTER or any other write.
- Only reference the tables listed above. Never reference users, np_beauty_profiles, \
np_chat_turns, np_tickets, or np_ticket_comments — they are out of scope for this chatbot, which \
answers questions about feedback and reviews only, never tickets.
- Every query touching np_feedback_items MUST filter source_type = 'review'.
- Do not invent columns — np_feedback_items has no product_id, brand, or category_id column; use \
the join path shown above.
- Match brand/category/subcategory/theme names case-insensitively — use ILIKE, never = — since \
the question's wording won't necessarily match the stored capitalization (e.g. b.name ILIKE \
'bella vita' matches a brand stored as "Bella Vita").
- Always include a LIMIT (200 or fewer) unless the question is a single aggregate (e.g. a COUNT).
- Give result columns short, simple, lowercase snake_case aliases (e.g. `AS review_count`) so \
they're easy to render in a table.
- Set chart_type to "bar", "line", or "pie" only when the question explicitly or implicitly asks \
for a chart/graph/comparison across categories or a trend over time; otherwise "none".
- When chart_type is not "none", x_field and y_field MUST exactly match two of your SELECT \
column aliases (x = the category/label axis, y = the numeric value axis), and y_label should be \
a short human-readable label for the y axis. When chart_type is "none", set x_field, y_field, \
and y_label to empty strings."""


SQL_PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "in_scope": {"type": "boolean"},
        "sql": {"type": "string"},
        "chart_type": {"type": "string", "enum": ["none", "bar", "line", "pie"]},
        "x_field": {"type": "string"},
        "y_field": {"type": "string"},
        "y_label": {"type": "string"},
    },
    "required": ["in_scope", "sql", "chart_type", "x_field", "y_field", "y_label"],
    "additionalProperties": False,
}

SUMMARY_SYSTEM_PROMPT = """You are a data analyst assistant summarizing a database query result \
for a product manager. Given their original question and a JSON preview of the result, write a \
short (2-4 sentence) plain-English answer that references concrete numbers/values from the data. \
Speak in business terms — never mention SQL, tables, or column names. If the result is empty, say \
so plainly."""

SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "string"}},
    "required": ["answer"],
    "additionalProperties": False,
}


class SqlGuardrailError(Exception):
    pass


_LEADING_SELECT_RE = re.compile(r"^\s*SELECT\b", re.IGNORECASE)
_TABLE_REF_RE = re.compile(r"\b(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)", re.IGNORECASE)
# EXTRACT(field FROM source), TRIM([...] FROM str), and SUBSTRING(str FROM n
# FOR m) are standard SQL functions that use a bare FROM/FOR keyword as part
# of their argument syntax, not a table clause — date-relative questions
# ("this week") routinely produce EXTRACT(...FROM...), so without stripping
# these first, _TABLE_REF_RE misreads e.g. "EXTRACT(DOW FROM CURRENT_DATE)"
# as a reference to a table named current_date and rejects a valid query.
_FROM_SYNTAX_FUNC_RE = re.compile(r"\b(?:EXTRACT|TRIM|SUBSTRING)\s*\([^)]*\)", re.IGNORECASE)
_BLOCKED_KEYWORDS = (
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "GRANT", "REVOKE",
    "CREATE", "CALL", "COPY", "MERGE", "VACUUM", "EXECUTE", "DO", "SET", "RESET",
    "LISTEN", "NOTIFY", "WITH",
)


def _validate_sql(sql: str) -> str:
    cleaned = sql.strip().rstrip(";").strip()
    if not cleaned:
        raise SqlGuardrailError("the generated query was empty")
    if ";" in cleaned:
        raise SqlGuardrailError("only a single statement is allowed")
    if "--" in cleaned or "/*" in cleaned:
        raise SqlGuardrailError("comments are not allowed in the query")
    if not _LEADING_SELECT_RE.match(cleaned):
        raise SqlGuardrailError("only SELECT queries are allowed")

    upper = cleaned.upper()
    for keyword in _BLOCKED_KEYWORDS:
        if re.search(rf"\b{keyword}\b", upper):
            raise SqlGuardrailError(f'the keyword "{keyword}" is not allowed')

    table_scan_text = _FROM_SYNTAX_FUNC_RE.sub(" ", cleaned)
    tables = {m.group(1).lower() for m in _TABLE_REF_RE.finditer(table_scan_text)}
    if not tables:
        raise SqlGuardrailError("no table reference found")
    disallowed = tables - ALLOWED_TABLES
    if disallowed:
        raise SqlGuardrailError(f"table(s) not allowed: {', '.join(sorted(disallowed))}")

    if not re.search(r"\bLIMIT\b", upper):
        cleaned += " LIMIT 200"
    return cleaned


@contextmanager
def _readonly_conn():
    if store._pool.closed:
        store._pool.open()
    with store._pool.connection() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        yield conn
        conn.rollback()


def _run_readonly(sql: str) -> list[dict]:
    with _readonly_conn() as conn:
        return conn.execute(sql).fetchall()


def _validate_plan(data: dict) -> dict:
    in_scope = bool(data.get("in_scope", True))
    sql = data.get("sql")
    if in_scope and (not isinstance(sql, str) or not sql.strip()):
        raise ValueError("missing sql in model response")
    chart_type = data.get("chart_type")
    if chart_type not in ("none", "bar", "line", "pie"):
        chart_type = "none"

    def _clean(key):
        value = data.get(key)
        return value.strip() if isinstance(value, str) and value.strip() else None

    return {
        "in_scope": in_scope,
        "sql": sql.strip() if isinstance(sql, str) else "",
        "chart_type": chart_type,
        "x_field": _clean("x_field"),
        "y_field": _clean("y_field"),
        "y_label": _clean("y_label"),
    }


def _call_plan_llm(provider: str, client, message: str, system_prompt: str, *, repair: bool = False, prior=None):
    """Provider-dispatch for one SQL_PLAN_SCHEMA-shaped call. `prior` is the
    previous turn's raw content to include in a repair request — a content
    block list for anthropic, a plain string for openai/groq (see
    llm_providers.call_anthropic/call_openai/call_groq). Returns
    (response, text) so callers can inspect refusal/finish_reason and reuse
    `response` as `prior` for a follow-up repair call."""
    if provider == "anthropic":
        response = llm.call_anthropic(client, message, system_prompt, SQL_PLAN_SCHEMA, repair=repair, prior_content=prior)
        text = next((b.text for b in response.content if b.type == "text"), "")
    else:
        call = llm.call_openai if provider == "openai" else llm.call_groq
        response = call(client, message, system_prompt, SQL_PLAN_SCHEMA, repair=repair, prior_text=prior)
        text = response.choices[0].message.content or ""
    return response, text


def _generate_plan(question: str) -> dict | None:
    """Mirrors classifier.py's _run_provider shape: one live attempt, one
    repair attempt, then give up (None) rather than guess at SQL."""
    providers = llm.available_providers()
    if not providers:
        return None
    provider = providers[0]
    client = llm.get_client(provider)
    transient_errors = llm.transient_errors_for(provider)
    system_prompt = _system_prompt(datetime.now(timezone.utc).date().isoformat())

    try:
        response, text = _call_plan_llm(provider, client, question, system_prompt)
        refused = response.stop_reason == "refusal" if provider == "anthropic" else response.choices[0].finish_reason == "content_filter"
        if refused:
            raise ValueError("model refused to answer")

        data = llm.extract_json(text)
        if data is None:
            raise ValueError("could not parse JSON from first response")
        return _validate_plan(data)

    except (ValueError, json.JSONDecodeError):
        try:
            prior = response.content if provider == "anthropic" else (response.choices[0].message.content or "")
            _, text = _call_plan_llm(provider, client, question, system_prompt, repair=True, prior=prior)
            data = llm.extract_json(text)
            if data is None:
                return None
            return _validate_plan(data)
        except Exception:
            return None

    except transient_errors:
        return None


def _repair_after_db_error(question: str, failed_sql: str, db_error: str) -> dict | None:
    """One extra attempt when a validated, guardrail-clean query still fails
    at the database (e.g. a hallucinated column) — feeds the real Postgres
    error back to the model, the same "show it what went wrong" idea as the
    JSON-repair path in _generate_plan above, just one level further down
    the pipeline."""
    providers = llm.available_providers()
    if not providers:
        return None
    provider = providers[0]
    client = llm.get_client(provider)
    system_prompt = _system_prompt(datetime.now(timezone.utc).date().isoformat())
    message = (
        f"{question}\n\nYour previous query failed with this Postgres error:\n{db_error}\n\n"
        f"Previous query:\n{failed_sql}\n\nWrite a corrected query that fixes this error."
    )
    try:
        _, text = _call_plan_llm(provider, client, message, system_prompt)
        data = llm.extract_json(text)
        if data is None:
            return None
        return _validate_plan(data)
    except Exception:
        return None


def _summarize(question: str, rows: list[dict], total: int) -> str:
    if total == 0:
        return "No matching rows were found for that question."
    providers = llm.available_providers()
    if not providers:
        return f"Found {total} matching row(s)."
    provider = providers[0]
    client = llm.get_client(provider)
    message = (
        f"Question: {question}\nTotal rows: {total}\n"
        f"Row preview (JSON, may be truncated): {json.dumps(rows[:25], default=str)}"
    )
    try:
        if provider == "anthropic":
            response = llm.call_anthropic(client, message, SUMMARY_SYSTEM_PROMPT, SUMMARY_SCHEMA, repair=False)
            text = next((b.text for b in response.content if b.type == "text"), "")
        else:
            call = llm.call_openai if provider == "openai" else llm.call_groq
            response = call(client, message, SUMMARY_SYSTEM_PROMPT, SUMMARY_SCHEMA, repair=False)
            text = response.choices[0].message.content or ""
        data = llm.extract_json(text)
        if data and isinstance(data.get("answer"), str) and data["answer"].strip():
            return data["answer"].strip()
    except Exception:
        pass
    return f"Found {total} matching row(s)."


def _result(*, answer: str, sql: str | None = None, columns=None, rows=None, chart=None, mode: str) -> dict:
    return {"answer": answer, "sql": sql, "columns": columns or [], "rows": rows or [], "chart": chart, "mode": mode}


def ask_question(question: str) -> dict:
    question = (question or "").strip()
    if not question:
        return _result(answer="Ask a question about the feedback or reviews.", mode="mock")

    if not llm.available_providers():
        return _result(
            answer=(
                "The analytics chatbot needs an LLM provider configured "
                "(ANTHROPIC_API_KEY, OPENAI_API_KEY, or GROQ_API_KEY) to turn questions into queries."
            ),
            mode="mock",
        )

    plan = _generate_plan(question)
    if plan is None:
        return _result(answer="I couldn't turn that into a query — try rephrasing your question.", mode="fallback")

    if not plan["in_scope"]:
        return _result(
            answer="I can't respond to this question — ask me about feedback and review analysis.",
            mode="off_topic",
        )

    try:
        sql = _validate_sql(plan["sql"])
    except SqlGuardrailError as exc:
        return _result(
            answer=f"I can't run that — {exc}. Try asking a read-only question about feedback or reviews.",
            sql=plan["sql"],
            mode="blocked",
        )

    try:
        rows = _run_readonly(sql)
    except Exception as exc:
        rows, sql, plan = _retry_after_db_error(question, sql, plan, exc)
        if rows is None:
            return _result(answer=f"That query didn't run: {exc}", sql=sql, mode="error")

    columns = list(rows[0].keys()) if rows else []
    answer = _summarize(question, rows, len(rows))
    chart = nykaa_chat_chart.build_chart_spec(plan["chart_type"], plan["x_field"], plan["y_field"], plan["y_label"], rows)
    return _result(answer=answer, sql=sql, columns=columns, rows=rows, chart=chart, mode="live")


def _retry_after_db_error(question: str, sql: str, plan: dict, exc: Exception) -> tuple[list[dict] | None, str, dict]:
    """Wraps _repair_after_db_error with guardrail re-validation and one
    execution retry. Falls back to (None, sql, plan) — the ORIGINAL sql/plan
    — on any failure, so the caller's error message still reflects what
    actually failed rather than an intermediate repair attempt."""
    repaired = _repair_after_db_error(question, sql, str(exc))
    if repaired is None or not repaired["in_scope"]:
        return None, sql, plan
    try:
        repaired_sql = _validate_sql(repaired["sql"])
        rows = _run_readonly(repaired_sql)
        return rows, repaired_sql, repaired
    except Exception:
        return None, sql, plan
