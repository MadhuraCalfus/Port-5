"""Postgres (Supabase) persistence layer.

Every routed ticket needs to survive a server restart, and it needs a real
audit trail (what did the AI decide, how confident was it, did a human
correct it, how long did it take) to back the analytics dashboard with real
numbers instead of made-up ones. Postgres — via Supabase — gives that a
managed home instead of a local file, which matters the moment this runs as
more than one process or on a host with an ephemeral filesystem.
"""
import atexit
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is required (a Postgres/Supabase connection string) — "
        "see .env.example for the format and where to find it in your Supabase project."
    )

ATTACHMENTS_DIR = Path(os.environ.get("TICKET_ATTACHMENTS_PATH", Path(__file__).parent.parent / "data" / "attachments"))

# Assumed average time a human agent spends reading, categorizing, and
# routing one ticket by hand. Used only when a real measured
# manual_time_seconds isn't provided (see the "Race Mode" feature in the UI,
# which records real stopwatch times instead of relying on this constant).
ASSUMED_MANUAL_SECONDS = 90.0

# One pool per process, opened lazily on first use and reused for the life of
# the app — a network round trip to open a fresh TCP+TLS connection per query
# is fine for a local SQLite file but not for a remote Postgres instance.
#
# keepalives_* make a dead-but-still-"open" connection (e.g. after the dev
# machine sleeps/wakes or switches networks) fail within ~60s instead of
# hanging on a TCP read with no timeout — without this, a request that grabs
# that connection just blocks forever, tying up a worker thread, and the
# whole app looks hung rather than erroring.
#
# No `check=` liveness probe: against a distant Postgres instance, that
# probe is itself a full extra network round-trip on every single pool
# checkout — with a query round-trip already costing several hundred ms
# here, that was roughly doubling the cost of every database call app-wide.
# keepalives_* above already catch a truly dead connection (surfacing as a
# real query error instead of being silently swapped out beforehand), which
# is the trade-off for the speed.
_pool = ConnectionPool(
    DATABASE_URL,
    min_size=1,
    max_size=10,
    kwargs={
        "row_factory": dict_row,
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 3,
        "connect_timeout": 10,
    },
    open=False,
)
atexit.register(_pool.close)

# Every id (users.id, team_members.id, tickets.id, tickets.user_id) is a
# plain SERIAL integer, assigned by Postgres itself — nothing in this module
# generates ids by hand.

_TICKETS_SCHEMA = """
    CREATE TABLE IF NOT EXISTS tickets (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        message TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'New',
        category TEXT,
        priority TEXT,
        team TEXT,
        tone TEXT,
        confidence REAL,
        is_ambiguous INTEGER,
        escalated INTEGER,
        reasoning TEXT,
        model_used TEXT,
        mode TEXT,
        latency_ms INTEGER,
        manual_time_seconds REAL,
        created_at TEXT NOT NULL,
        baseline_json TEXT,
        reviewed INTEGER NOT NULL DEFAULT 0,
        corrected_category TEXT,
        corrected_priority TEXT,
        corrected_team TEXT,
        feedback_note TEXT,
        model_results_json TEXT
    )
"""

_TICKET_COMMENTS_SCHEMA = """
    CREATE TABLE IF NOT EXISTS ticket_comments (
        id SERIAL PRIMARY KEY,
        ticket_id INTEGER NOT NULL,
        author_role TEXT NOT NULL,
        author_name TEXT NOT NULL,
        body TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
"""

_TICKET_COMMENT_READS_SCHEMA = """
    CREATE TABLE IF NOT EXISTS ticket_comment_reads (
        ticket_id INTEGER NOT NULL,
        viewer_role TEXT NOT NULL,
        viewer_key TEXT NOT NULL,
        last_read_at TEXT NOT NULL,
        PRIMARY KEY (ticket_id, viewer_role, viewer_key)
    )
"""

# A customer whose issue AI resolved before any ticket ever existed — logged
# separately from `tickets` (rather than as a ticket with some new status)
# because these never got a category/priority/team/status lifecycle at all;
# they're a distinct kind of event: AI handled it, no human/team involved.
_SELF_RESOLVED_SCHEMA = """
    CREATE TABLE IF NOT EXISTS self_resolved (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        message TEXT NOT NULL,
        summary TEXT,
        steps_json TEXT,
        created_at TEXT NOT NULL
    )
"""

# The PM dashboard's unified feedback log — one row per piece of customer
# voice regardless of where it came from. source_ref points back at
# tickets.id when source_type = 'ticket' (a ticket is mirrored here, not
# moved — the ticket row and its routing lifecycle are untouched); it's NULL
# for 'review'/'survey' rows, which have no other home in this app.
# sentiment/category/theme/urgency/is_actionable_ticket start NULL and are
# filled in by the AI analysis pipeline (a later phase) — this table exists
# first so ingestion can start independently of that pipeline being built.
# category is the closed top-level taxonomy (models.FeedbackCategory); theme
# is a finer-grained, free-text sub-topic within it.
_FEEDBACK_ITEMS_SCHEMA = """
    CREATE TABLE IF NOT EXISTS feedback_items (
        id SERIAL PRIMARY KEY,
        source_type TEXT NOT NULL,
        source_ref INTEGER,
        user_id INTEGER,
        text TEXT NOT NULL,
        sentiment_label TEXT,
        sentiment_score REAL,
        category TEXT,
        theme TEXT,
        urgency_score REAL,
        is_actionable_ticket INTEGER,
        rating INTEGER,
        model_used TEXT,
        mode TEXT,
        latency_ms INTEGER,
        created_at TEXT NOT NULL
    )
"""

# One persisted report per (period_type, period_key) — generated on demand,
# not recomputed on every dashboard view, so repeat views of the same period
# show identical numbers and narrative. UNIQUE lets "regenerate this period"
# be an upsert instead of accumulating duplicates.
_PERIODIC_INSIGHTS_SCHEMA = """
    CREATE TABLE IF NOT EXISTS periodic_insights (
        id SERIAL PRIMARY KEY,
        period_type TEXT NOT NULL,
        period_key TEXT NOT NULL,
        period_start TEXT NOT NULL,
        period_end TEXT NOT NULL,
        category_trend_json TEXT,
        sentiment_trend_json TEXT,
        narrative_json TEXT,
        model_used TEXT,
        mode TEXT,
        generated_at TEXT NOT NULL,
        UNIQUE (period_type, period_key)
    )
"""

# AI-recommended actions for improving a category's sentiment. Anchored to
# (period_type, period_key) directly rather than requiring a periodic_insights
# row to exist first — trend-based actions (this phase) are generated before
# the narrative-report table gets its first row (a later phase); insight_id
# is filled in only once a report generation links the two. Tracked with a
# simple done/not-done status a PM can toggle — not a full workflow, just
# enough to show which recommendations have been acted on.
_RECOMMENDED_ACTIONS_SCHEMA = """
    CREATE TABLE IF NOT EXISTS recommended_actions (
        id SERIAL PRIMARY KEY,
        period_type TEXT NOT NULL,
        period_key TEXT NOT NULL,
        insight_id INTEGER,
        category TEXT,
        action_text TEXT NOT NULL,
        rationale TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT NOT NULL
    )
"""

# PM-authored ad-hoc surveys (distinct from the fixed 1-5 star + comment
# survey in feedback_items/feedback_ai — these are one-off structured
# question sets the PM writes themselves, never touching the AI pipeline).
# One shared scale per survey; the questions are a JSON list rather than a
# child table.
_CUSTOM_SURVEYS_SCHEMA = """
    CREATE TABLE IF NOT EXISTS custom_surveys (
        id SERIAL PRIMARY KEY,
        title TEXT NOT NULL,
        scale_points INTEGER NOT NULL,
        questions_json TEXT NOT NULL,
        created_by TEXT,
        status TEXT NOT NULL DEFAULT 'draft',
        created_at TEXT NOT NULL,
        sent_at TEXT
    )
"""

# One row per (survey, customer) response — UNIQUE enforces "answer once".
_SURVEY_RESPONSES_SCHEMA = """
    CREATE TABLE IF NOT EXISTS survey_responses (
        id SERIAL PRIMARY KEY,
        survey_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        answers_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE (survey_id, user_id)
    )
"""

_sandbox_user_id: int | None = None


@contextmanager
def _conn():
    if _pool.closed:
        _pool.open()
    with _pool.connection() as conn:
        yield conn
        conn.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _existing_columns(conn, table: str) -> set[str]:
    rows = conn.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = %s", (table,)
    ).fetchall()
    return {r["column_name"] for r in rows}


def init_db() -> None:
    global _sandbox_user_id
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS team_members (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                team TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        # Added after the table already existed in some databases — Postgres
        # can add nullable columns in place, no full-table migration needed.
        member_cols = _existing_columns(conn, "team_members")
        if "reset_token" not in member_cols:
            conn.execute("ALTER TABLE team_members ADD COLUMN reset_token TEXT")
        if "reset_token_expires" not in member_cols:
            conn.execute("ALTER TABLE team_members ADD COLUMN reset_token_expires TEXT")
        conn.execute(_TICKETS_SCHEMA)
        conn.execute(_TICKET_COMMENTS_SCHEMA)
        conn.execute(_TICKET_COMMENT_READS_SCHEMA)
        conn.execute(_SELF_RESOLVED_SCHEMA)
        conn.execute(_FEEDBACK_ITEMS_SCHEMA)
        conn.execute(_PERIODIC_INSIGHTS_SCHEMA)
        conn.execute(_RECOMMENDED_ACTIONS_SCHEMA)
        conn.execute(_CUSTOM_SURVEYS_SCHEMA)
        conn.execute(_SURVEY_RESPONSES_SCHEMA)


        # feedback_items initially shipped with no user_id — added so the PM
        # dashboard can group a customer's tickets/surveys by who submitted
        # them; imported reviews have no account behind them and stay NULL.
        feedback_cols = _existing_columns(conn, "feedback_items")
        if "user_id" not in feedback_cols:
            conn.execute("ALTER TABLE feedback_items ADD COLUMN user_id INTEGER")
        if "rating" not in feedback_cols:
            conn.execute("ALTER TABLE feedback_items ADD COLUMN rating INTEGER")

        # Category/theme taxonomy split: the old flat `theme` column (9 fixed
        # values) becomes `category` (11 fixed top-level values) plus a new,
        # finer-grained free-text `theme` column (e.g. "Password Reset" under
        # "Login & Account"). The rename preserves existing rows' data as-is;
        # a one-off reclassification script re-analyzes old rows into the new
        # taxonomy afterward, since the split isn't a pure rename (see
        # models.FeedbackCategory). Same rename applies to recommended_actions
        # below, which stays at category granularity only (no new theme column).
        if "category" not in feedback_cols and "theme" in feedback_cols:
            conn.execute("ALTER TABLE feedback_items RENAME COLUMN theme TO category")
            feedback_cols = _existing_columns(conn, "feedback_items")
        if "theme" not in feedback_cols:
            conn.execute("ALTER TABLE feedback_items ADD COLUMN theme TEXT")

        action_cat_cols = _existing_columns(conn, "recommended_actions")
        if "category" not in action_cat_cols and "theme" in action_cat_cols:
            conn.execute("ALTER TABLE recommended_actions RENAME COLUMN theme TO category")

        # recommended_actions initially shipped with insight_id NOT NULL and
        # no period_type/period_key — corrected before this table had any
        # real data, but a database created from that first version still
        # needs the column added and the NOT NULL relaxed.
        action_cols = _existing_columns(conn, "recommended_actions")
        if "period_type" not in action_cols:
            conn.execute("ALTER TABLE recommended_actions ADD COLUMN period_type TEXT")
        if "period_key" not in action_cols:
            conn.execute("ALTER TABLE recommended_actions ADD COLUMN period_key TEXT")
        conn.execute("ALTER TABLE recommended_actions ALTER COLUMN insight_id DROP NOT NULL")

        # periodic_insights initially shipped keyed on (period_type,
        # period_start) with no period_key column — corrected before this
        # table had any real data, but a database created from that first
        # version still needs the column added and re-keyed.
        insight_cols = _existing_columns(conn, "periodic_insights")
        if "period_key" not in insight_cols:
            conn.execute("ALTER TABLE periodic_insights ADD COLUMN period_key TEXT")
            conn.execute("UPDATE periodic_insights SET period_key = period_start WHERE period_key IS NULL")
            conn.execute(
                "ALTER TABLE periodic_insights ADD CONSTRAINT periodic_insights_period_type_period_key_key "
                "UNIQUE (period_type, period_key)"
            )
        if "category_trend_json" not in insight_cols and "theme_trend_json" in insight_cols:
            conn.execute("ALTER TABLE periodic_insights RENAME COLUMN theme_trend_json TO category_trend_json")

        # Attachment support added after ticket_comments already existed in
        # some databases — same in-place nullable-column pattern as above.
        # attachment_path is legacy (files used to live on disk); attachments
        # are now stored directly in the database as attachment_data.
        comment_cols = _existing_columns(conn, "ticket_comments")
        for col in ("attachment_path", "attachment_name", "attachment_mime"):
            if col not in comment_cols:
                conn.execute(f"ALTER TABLE ticket_comments ADD COLUMN {col} TEXT")
        if "attachment_data" not in comment_cols:
            conn.execute("ALTER TABLE ticket_comments ADD COLUMN attachment_data BYTEA")

        # One-time backfill: any row still pointing at an on-disk file (from
        # before attachments moved into the database) gets its bytes pulled
        # in now, so downloads keep working uniformly through attachment_data
        # regardless of when the attachment was originally uploaded.
        rows = conn.execute(
            "SELECT id, attachment_path FROM ticket_comments WHERE attachment_path IS NOT NULL AND attachment_data IS NULL"
        ).fetchall()
        for row in rows:
            file_path = ATTACHMENTS_DIR / row["attachment_path"]
            if file_path.exists():
                conn.execute(
                    "UPDATE ticket_comments SET attachment_data = %s WHERE id = %s",
                    (file_path.read_bytes(), row["id"]),
                )

        # A placeholder account tickets can be attached to when there's no
        # real signed-up customer behind them — the Admin sandbox tools
        # (Route a Ticket / Race / Demo) classify ad-hoc text, not a real
        # customer's submitted ticket. ON CONFLICT DO NOTHING keyed by the
        # unique email means this only actually inserts once, ever; every
        # later startup just looks its id back up.
        conn.execute(
            """INSERT INTO users (name, email, password_hash, created_at) VALUES (%s, %s, %s, %s)
               ON CONFLICT (email) DO NOTHING""",
            ("Admin sandbox", "sandbox@internal", "!", _now()),
        )
        _sandbox_user_id = conn.execute(
            "SELECT id FROM users WHERE email = 'sandbox@internal'"
        ).fetchone()["id"]


def _sandbox_user() -> int:
    assert _sandbox_user_id is not None, "store.init_db() must run before saving sandbox tickets"
    return _sandbox_user_id


# ---- users ---------------------------------------------------------------

def create_user(name: str, email: str, password_hash: str) -> dict:
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO users (name, email, password_hash, created_at) VALUES (%s, %s, %s, %s) RETURNING id",
            (name, email, password_hash, _now()),
        )
        return {"id": cur.fetchone()["id"], "name": name, "email": email}


def get_user_by_email(email: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = %s", (email,)).fetchone()
        return dict(row) if row else None


# ---- team members ----------------------------------------------------------

def create_team_member(name: str, email: str, password_hash: str, team: str) -> dict:
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO team_members (name, email, password_hash, team, created_at) VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (name, email, password_hash, team, _now()),
        )
        return {"id": cur.fetchone()["id"], "name": name, "email": email, "team": team}


def get_team_member_by_email(email: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM team_members WHERE email = %s", (email,)).fetchone()
        return dict(row) if row else None


def list_team_members() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute("SELECT id, name, email, team, created_at FROM team_members ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


def get_team_member_by_id(member_id: int) -> dict | None:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM team_members WHERE id = %s", (member_id,)).fetchone()
        return dict(row) if row else None


def delete_team_member(member_id: int) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM team_members WHERE id = %s", (member_id,))


def update_team_member_password(member_id: int, password_hash: str) -> None:
    with _conn() as conn:
        conn.execute("UPDATE team_members SET password_hash = %s WHERE id = %s", (password_hash, member_id))


def set_team_member_reset_token(member_id: int, token: str, expires_at: str) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE team_members SET reset_token = %s, reset_token_expires = %s WHERE id = %s",
            (token, expires_at, member_id),
        )


def get_team_member_by_reset_token(token: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM team_members WHERE reset_token = %s", (token,)).fetchone()
        return dict(row) if row else None


def clear_team_member_reset_token(member_id: int) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE team_members SET reset_token = NULL, reset_token_expires = NULL WHERE id = %s", (member_id,)
        )


# ---- tickets ---------------------------------------------------------------

def create_ticket(user_id: int, message: str) -> dict:
    """A brand-new, unrouted ticket submitted by a user — no AI call yet."""
    with _conn() as conn:
        row = conn.execute(
            "INSERT INTO tickets (user_id, message, status, created_at) VALUES (%s, %s, 'New', %s) RETURNING *",
            (user_id, message, _now()),
        ).fetchone()
        return _row_to_dict(row)


def save_ticket(result: dict) -> int:
    """Insert an already-fully-classified ticket — used by the Admin sandbox
    tools (Route a Ticket / Race / Demo), which classify ad-hoc text in one
    call rather than routing a real customer-submitted ticket later. Returns
    the id Postgres assigned it."""
    with _conn() as conn:
        cur = conn.execute(
            """INSERT INTO tickets (
                user_id, message, status, category, priority, team, tone, confidence, is_ambiguous,
                escalated, reasoning, model_used, mode, latency_ms, manual_time_seconds,
                created_at, baseline_json, model_results_json
            ) VALUES (%s, %s, 'Routed', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id""",
            (
                _sandbox_user(), result["message"], result["category"], result["priority"],
                result["team"], result["tone"], result["confidence"], int(result["is_ambiguous"]),
                int(result["escalated"]), result["reasoning"], result["model_used"], result["mode"],
                result["latency_ms"], result.get("manual_time_seconds"), result["created_at"],
                json.dumps(result["baseline"]) if result.get("baseline") else None,
                json.dumps(result["model_results"]) if result.get("model_results") else None,
            ),
        )
        return cur.fetchone()["id"]


def apply_classification(ticket_id: int, result: dict) -> dict | None:
    """Fill in the AI classification on an existing (previously unrouted)
    ticket — what an Admin's "Route" action does. Moves status New -> Routed."""
    with _conn() as conn:
        row = conn.execute(
            """UPDATE tickets SET
                status = 'Routed', category = %s, priority = %s, team = %s, tone = %s, confidence = %s,
                is_ambiguous = %s, escalated = %s, reasoning = %s, model_used = %s, mode = %s, latency_ms = %s,
                baseline_json = %s, model_results_json = %s
               WHERE id = %s RETURNING *""",
            (
                result["category"], result["priority"], result["team"], result["tone"], result["confidence"],
                int(result["is_ambiguous"]), int(result["escalated"]), result["reasoning"], result["model_used"],
                result["mode"], result["latency_ms"],
                json.dumps(result["baseline"]) if result.get("baseline") else None,
                json.dumps(result["model_results"]) if result.get("model_results") else None,
                ticket_id,
            ),
        ).fetchone()
        return _row_to_dict(row) if row else None


def update_ticket_status(ticket_id: int, status: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "UPDATE tickets SET status = %s WHERE id = %s RETURNING *", (status, ticket_id)
        ).fetchone()
        return _row_to_dict(row) if row else None


def save_feedback(ticket_id: int, corrected_category: str | None, corrected_priority: str | None,
                   corrected_team: str | None, note: str | None) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            """UPDATE tickets SET reviewed = 1, corrected_category = %s, corrected_priority = %s,
               corrected_team = %s, feedback_note = %s WHERE id = %s RETURNING *""",
            (corrected_category, corrected_priority, corrected_team, note, ticket_id),
        ).fetchone()
        return _row_to_dict(row) if row else None


def _row_to_dict(row: dict) -> dict:
    d = dict(row)
    d["is_ambiguous"] = bool(d["is_ambiguous"]) if d["is_ambiguous"] is not None else None
    d["escalated"] = bool(d["escalated"]) if d["escalated"] is not None else None
    d["reviewed"] = bool(d["reviewed"])
    d["baseline"] = json.loads(d.pop("baseline_json")) if d.get("baseline_json") else None
    d["model_results"] = json.loads(d.pop("model_results_json")) if d.get("model_results_json") else None
    return d


def get_ticket(ticket_id: int) -> dict | None:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM tickets WHERE id = %s", (ticket_id,)).fetchone()
        return _row_to_dict(row) if row else None


def get_ticket_with_user(ticket_id: int) -> dict | None:
    """Same as get_ticket, joined with the submitting user's name/email —
    powers the per-ticket PDF report."""
    with _conn() as conn:
        row = conn.execute(
            """SELECT tickets.*, users.name AS user_name, users.email AS user_email
               FROM tickets JOIN users ON tickets.user_id = users.id
               WHERE tickets.id = %s""",
            (ticket_id,),
        ).fetchone()
        return _row_to_dict(row) if row else None


def list_tickets(limit: int = 50, offset: int = 0) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM tickets ORDER BY created_at DESC LIMIT %s OFFSET %s", (limit, offset)
        ).fetchall()
        return [_row_to_dict(r) for r in rows]


def list_tickets_for_user(user_id: int) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM tickets WHERE user_id = %s ORDER BY created_at DESC", (user_id,)
        ).fetchall()
        return [_row_to_dict(r) for r in rows]


def list_tickets_by_status(status: str) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            """SELECT tickets.*, users.name AS user_name, users.email AS user_email
               FROM tickets JOIN users ON tickets.user_id = users.id
               WHERE tickets.status = %s ORDER BY tickets.created_at ASC""",
            (status,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]


def list_tickets_for_team(team: str) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            """SELECT tickets.*, users.name AS user_name, users.email AS user_email
               FROM tickets JOIN users ON tickets.user_id = users.id
               WHERE tickets.team = %s AND tickets.status != 'New'
               ORDER BY tickets.created_at DESC""",
            (team,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]


def list_known_teams() -> list[str]:
    """Teams that actually exist in this deployment — have a team member or
    at least one ticket ever routed to them — rather than every team in the
    fixed classification enum."""
    with _conn() as conn:
        rows = conn.execute(
            """SELECT team FROM team_members
               UNION
               SELECT team FROM tickets WHERE team IS NOT NULL"""
        ).fetchall()
        return sorted({r["team"] for r in rows})


def list_tickets_with_user(limit: int = 200, offset: int = 0) -> list[dict]:
    """Full detail across all tickets, joined with the submitting user's
    name/email — powers the Admin "all tickets" detail view."""
    with _conn() as conn:
        rows = conn.execute(
            """SELECT tickets.*, users.name AS user_name, users.email AS user_email
               FROM tickets JOIN users ON tickets.user_id = users.id
               ORDER BY tickets.created_at DESC LIMIT %s OFFSET %s""",
            (limit, offset),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]


def count_tickets() -> int:
    with _conn() as conn:
        return conn.execute("SELECT COUNT(*) AS n FROM tickets").fetchone()["n"]


# ---- self-resolved (AI helped, customer confirmed, no ticket ever raised) --

def save_self_resolved(user_id: int, message: str, summary: str | None, steps: list[str]) -> dict:
    with _conn() as conn:
        row = conn.execute(
            """INSERT INTO self_resolved (user_id, message, summary, steps_json, created_at)
               VALUES (%s, %s, %s, %s, %s) RETURNING *""",
            (user_id, message, summary, json.dumps(steps), _now()),
        ).fetchone()
        return _self_resolved_row_to_dict(row)


def list_self_resolved(limit: int = 200, offset: int = 0) -> list[dict]:
    """Joined with the customer's name/email — powers the Admin "AI Resolved" view."""
    with _conn() as conn:
        rows = conn.execute(
            """SELECT self_resolved.*, users.name AS user_name, users.email AS user_email
               FROM self_resolved JOIN users ON self_resolved.user_id = users.id
               ORDER BY self_resolved.created_at DESC LIMIT %s OFFSET %s""",
            (limit, offset),
        ).fetchall()
        return [_self_resolved_row_to_dict(r) for r in rows]


def list_self_resolved_for_user(user_id: int) -> list[dict]:
    """One customer's own AI-resolved history — powers their 'Resolved by AI'
    tab, the self-service mirror of list_tickets_for_user."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM self_resolved WHERE user_id = %s ORDER BY created_at DESC", (user_id,)
        ).fetchall()
        return [_self_resolved_row_to_dict(r) for r in rows]


def count_self_resolved() -> int:
    with _conn() as conn:
        return conn.execute("SELECT COUNT(*) AS n FROM self_resolved").fetchone()["n"]


def _self_resolved_row_to_dict(row: dict) -> dict:
    d = dict(row)
    d["steps"] = json.loads(d.pop("steps_json")) if d.get("steps_json") else []
    return d


# ---- feedback items (PM insights: unified ticket/review/survey log) ------

def save_feedback_item(
    source_type: str,
    text: str,
    sentiment_label: str,
    sentiment_score: float,
    category: str,
    urgency_score: float,
    is_actionable_ticket: bool | None,
    model_used: str,
    mode: str,
    latency_ms: int,
    source_ref: int | None = None,
    user_id: int | None = None,
    rating: int | None = None,
    theme: str | None = None,
    created_at: str | None = None,
) -> dict:
    with _conn() as conn:
        row = conn.execute(
            """INSERT INTO feedback_items (
                source_type, source_ref, user_id, text, sentiment_label, sentiment_score, category, theme,
                urgency_score, is_actionable_ticket, rating, model_used, mode, latency_ms, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *""",
            (
                source_type, source_ref, user_id, text, sentiment_label, sentiment_score, category, theme,
                urgency_score, int(is_actionable_ticket) if is_actionable_ticket is not None else None,
                rating, model_used, mode, latency_ms, created_at or _now(),
            ),
        ).fetchone()
        return _feedback_item_row_to_dict(row)


def list_feedback_items(limit: int = 100000, offset: int = 0) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM feedback_items ORDER BY created_at DESC LIMIT %s OFFSET %s", (limit, offset)
        ).fetchall()
        return [_feedback_item_row_to_dict(r) for r in rows]


def list_feedback_items_between(start: str, end_exclusive: str) -> list[dict]:
    """Every feedback_items row with created_at in [start, end_exclusive) —
    used to export exactly one period's worth of data (PDF/CSV), independent
    of the `limit` cap list_feedback_items applies for dashboard views."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM feedback_items WHERE created_at >= %s AND created_at < %s ORDER BY created_at ASC",
            (start, end_exclusive),
        ).fetchall()
        return [_feedback_item_row_to_dict(r) for r in rows]


def _feedback_item_row_to_dict(row: dict) -> dict:
    d = dict(row)
    d["is_actionable_ticket"] = bool(d["is_actionable_ticket"]) if d["is_actionable_ticket"] is not None else None
    return d


def update_feedback_analysis(
    item_id: int,
    text: str,
    category: str,
    theme: str,
    sentiment_label: str,
    sentiment_score: float,
    urgency_score: float,
    is_actionable_ticket: bool,
    model_used: str,
    mode: str,
) -> dict | None:
    """Re-analyze one existing feedback_items row in place — used by the
    one-off reclassify_feedback.py maintenance script when the category/
    theme taxonomy changes. Overwrites `text` too, so a legacy survey row's
    display bug (raw "Survey rating: N/5..." text) can be cleaned up in the
    same pass as its re-classification."""
    with _conn() as conn:
        row = conn.execute(
            """UPDATE feedback_items SET
                text = %s, category = %s, theme = %s, sentiment_label = %s, sentiment_score = %s,
                urgency_score = %s, is_actionable_ticket = %s, model_used = %s, mode = %s
               WHERE id = %s RETURNING *""",
            (
                text, category, theme, sentiment_label, sentiment_score, urgency_score,
                int(is_actionable_ticket), model_used, mode, item_id,
            ),
        ).fetchone()
        return _feedback_item_row_to_dict(row) if row else None


# ---- recommended actions (AI suggestions per category, per period) -------

def save_recommended_action(period_type: str, period_key: str, category: str | None, action_text: str, rationale: str | None) -> dict:
    with _conn() as conn:
        row = conn.execute(
            """INSERT INTO recommended_actions (period_type, period_key, category, action_text, rationale, status, created_at)
               VALUES (%s, %s, %s, %s, %s, 'pending', %s) RETURNING *""",
            (period_type, period_key, category, action_text, rationale, _now()),
        ).fetchone()
        return dict(row)


def list_recommended_actions(period_type: str, period_key: str) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            """SELECT * FROM recommended_actions WHERE period_type = %s AND period_key = %s
               ORDER BY created_at ASC""",
            (period_type, period_key),
        ).fetchall()
        return [dict(r) for r in rows]


def update_action_status(action_id: int, status: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "UPDATE recommended_actions SET status = %s WHERE id = %s RETURNING *", (status, action_id)
        ).fetchone()
        return dict(row) if row else None


def link_actions_to_insight(period_type: str, period_key: str, insight_id: int) -> None:
    """Back-fills insight_id on whatever recommended_actions were generated
    for this period before a report existed to link them to (actions can be
    generated independently of a report — see recommended_actions' schema
    comment). Only touches rows that aren't already linked, so re-generating
    a report doesn't reassign actions that already point at an older one."""
    with _conn() as conn:
        conn.execute(
            """UPDATE recommended_actions SET insight_id = %s
               WHERE period_type = %s AND period_key = %s AND insight_id IS NULL""",
            (insight_id, period_type, period_key),
        )


# ---- periodic insights (persisted daily/weekly/monthly/yearly reports) ---

def upsert_periodic_insight(
    period_type: str,
    period_key: str,
    period_start: str,
    period_end: str,
    category_trend: dict,
    sentiment_trend: dict,
    narrative: dict,
    model_used: str,
    mode: str,
) -> dict:
    with _conn() as conn:
        row = conn.execute(
            """INSERT INTO periodic_insights (
                period_type, period_key, period_start, period_end, category_trend_json,
                sentiment_trend_json, narrative_json, model_used, mode, generated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (period_type, period_key) DO UPDATE SET
                period_start = EXCLUDED.period_start, period_end = EXCLUDED.period_end,
                category_trend_json = EXCLUDED.category_trend_json, sentiment_trend_json = EXCLUDED.sentiment_trend_json,
                narrative_json = EXCLUDED.narrative_json, model_used = EXCLUDED.model_used,
                mode = EXCLUDED.mode, generated_at = EXCLUDED.generated_at
            RETURNING *""",
            (
                period_type, period_key, period_start, period_end, json.dumps(category_trend),
                json.dumps(sentiment_trend), json.dumps(narrative), model_used, mode, _now(),
            ),
        ).fetchone()
        return _periodic_insight_row_to_dict(row)


def get_periodic_insight(period_type: str, period_key: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM periodic_insights WHERE period_type = %s AND period_key = %s",
            (period_type, period_key),
        ).fetchone()
        return _periodic_insight_row_to_dict(row) if row else None


def _periodic_insight_row_to_dict(row: dict) -> dict:
    d = dict(row)
    d["category_trend"] = json.loads(d.pop("category_trend_json")) if d.get("category_trend_json") else None
    d["sentiment_trend"] = json.loads(d.pop("sentiment_trend_json")) if d.get("sentiment_trend_json") else None
    d["narrative"] = json.loads(d.pop("narrative_json")) if d.get("narrative_json") else None
    return d


# ---- custom surveys (PM-authored, ad-hoc question sets) -------------------

def create_custom_survey(title: str, scale_points: int, questions: list[str], created_by: str | None) -> dict:
    with _conn() as conn:
        row = conn.execute(
            """INSERT INTO custom_surveys (title, scale_points, questions_json, created_by, status, created_at)
               VALUES (%s, %s, %s, %s, 'draft', %s) RETURNING *""",
            (title, scale_points, json.dumps(questions), created_by, _now()),
        ).fetchone()
        return _custom_survey_row_to_dict(row)


def list_custom_surveys() -> list[dict]:
    """Every survey the PM has authored, most recent first, with how many
    customers have answered it so far — one query rather than N+1 since the
    Create Survey tab's table needs the count for every row at once."""
    with _conn() as conn:
        rows = conn.execute(
            """SELECT custom_surveys.*, COUNT(survey_responses.id) AS response_count
               FROM custom_surveys
               LEFT JOIN survey_responses ON survey_responses.survey_id = custom_surveys.id
               GROUP BY custom_surveys.id
               ORDER BY custom_surveys.created_at DESC"""
        ).fetchall()
        return [_custom_survey_row_to_dict(r) for r in rows]


def get_custom_survey(survey_id: int) -> dict | None:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM custom_surveys WHERE id = %s", (survey_id,)).fetchone()
        return _custom_survey_row_to_dict(row) if row else None


def mark_survey_sent(survey_id: int) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "UPDATE custom_surveys SET status = 'sent', sent_at = %s WHERE id = %s RETURNING *",
            (_now(), survey_id),
        ).fetchone()
        return _custom_survey_row_to_dict(row) if row else None


def list_pending_surveys_for_user(user_id: int) -> list[dict]:
    """Every sent survey this customer hasn't answered yet, oldest first —
    the floating "hey, new survey" card on the customer's Feedback Survey
    tab works through these one at a time."""
    with _conn() as conn:
        rows = conn.execute(
            """SELECT custom_surveys.* FROM custom_surveys
               LEFT JOIN survey_responses
                 ON survey_responses.survey_id = custom_surveys.id AND survey_responses.user_id = %s
               WHERE custom_surveys.status = 'sent' AND survey_responses.id IS NULL
               ORDER BY custom_surveys.sent_at ASC""",
            (user_id,),
        ).fetchall()
        return [_custom_survey_row_to_dict(r) for r in rows]


def save_survey_response(survey_id: int, user_id: int, answers: list[int]) -> dict | None:
    """ON CONFLICT DO NOTHING backed by UNIQUE(survey_id, user_id) — a
    customer answering the same survey twice (e.g. a double-submit) is a
    safe no-op rather than an error."""
    with _conn() as conn:
        row = conn.execute(
            """INSERT INTO survey_responses (survey_id, user_id, answers_json, created_at)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (survey_id, user_id) DO NOTHING
               RETURNING *""",
            (survey_id, user_id, json.dumps(answers), _now()),
        ).fetchone()
        return _survey_response_row_to_dict(row) if row else None


def list_survey_responses(survey_id: int) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM survey_responses WHERE survey_id = %s", (survey_id,)).fetchall()
        return [_survey_response_row_to_dict(r) for r in rows]


def _custom_survey_row_to_dict(row: dict) -> dict:
    d = dict(row)
    d["questions"] = json.loads(d.pop("questions_json"))
    return d


def _survey_response_row_to_dict(row: dict) -> dict:
    d = dict(row)
    d["answers"] = json.loads(d.pop("answers_json"))
    return d


# ---- ticket comments (customer <-> team messaging on one ticket) --------

# Every JSON-facing read of a comment excludes attachment_data — it's a
# potentially large BYTEA that isn't JSON-serializable anyway. Only
# get_ticket_comment (used solely by the file-download endpoint, which
# returns raw bytes, never JSON) selects it.
_COMMENT_JSON_COLUMNS = "id, ticket_id, author_role, author_name, body, created_at, attachment_name, attachment_mime"


def add_ticket_comment(
    ticket_id: int,
    author_role: str,
    author_name: str,
    body: str,
    attachment_data: bytes | None = None,
    attachment_name: str | None = None,
    attachment_mime: str | None = None,
) -> dict:
    with _conn() as conn:
        row = conn.execute(
            f"""INSERT INTO ticket_comments
               (ticket_id, author_role, author_name, body, created_at, attachment_data, attachment_name, attachment_mime)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING {_COMMENT_JSON_COLUMNS}""",
            (ticket_id, author_role, author_name, body, _now(), attachment_data, attachment_name, attachment_mime),
        ).fetchone()
        return dict(row)


def get_ticket_comment(comment_id: int) -> dict | None:
    """Includes attachment_data — only call this from the file-download
    endpoint, never anywhere the result gets JSON-serialized."""
    with _conn() as conn:
        row = conn.execute("SELECT * FROM ticket_comments WHERE id = %s", (comment_id,)).fetchone()
        return dict(row) if row else None


def list_ticket_comments(ticket_id: int) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            f"SELECT {_COMMENT_JSON_COLUMNS} FROM ticket_comments WHERE ticket_id = %s ORDER BY created_at ASC",
            (ticket_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def list_ticket_comments_with_attachments(ticket_id: int) -> list[dict]:
    """Includes attachment_data — only for the PDF report generator, which
    reads the raw bytes to embed/merge attachments. Never JSON-serialize
    this; use list_ticket_comments for anything API-facing."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM ticket_comments WHERE ticket_id = %s ORDER BY created_at ASC", (ticket_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def mark_comments_read(ticket_id: int, viewer_role: str, viewer_key: str) -> None:
    with _conn() as conn:
        conn.execute(
            """INSERT INTO ticket_comment_reads (ticket_id, viewer_role, viewer_key, last_read_at)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (ticket_id, viewer_role, viewer_key) DO UPDATE SET last_read_at = EXCLUDED.last_read_at""",
            (ticket_id, viewer_role, viewer_key, _now()),
        )


def unread_comment_counts(ticket_ids: list[int], viewer_role: str, viewer_key: str) -> dict[int, int]:
    """How many comments from the OTHER side are newer than this viewer's
    last read, per ticket — powers the badge on the message icon."""
    if not ticket_ids:
        return {}
    with _conn() as conn:
        placeholders = ",".join("%s" for _ in ticket_ids)
        last_reads = {
            row["ticket_id"]: row["last_read_at"]
            for row in conn.execute(
                f"""SELECT ticket_id, last_read_at FROM ticket_comment_reads
                    WHERE viewer_role = %s AND viewer_key = %s AND ticket_id IN ({placeholders})""",
                (viewer_role, viewer_key, *ticket_ids),
            ).fetchall()
        }
        rows = conn.execute(
            f"""SELECT ticket_id, created_at FROM ticket_comments
                WHERE ticket_id IN ({placeholders}) AND author_role != %s""",
            (*ticket_ids, viewer_role),
        ).fetchall()
        counts: dict[int, int] = {}
        for r in rows:
            last_read = last_reads.get(r["ticket_id"])
            if last_read is None or r["created_at"] > last_read:
                counts[r["ticket_id"]] = counts.get(r["ticket_id"], 0) + 1
        return counts
