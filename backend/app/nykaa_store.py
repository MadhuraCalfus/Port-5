"""Nykaa Pulse — cosmetics catalog & order persistence.

Additive layer on top of store.py's existing Postgres connection pool: reuses
_conn()/_now()/_existing_columns() from there rather than opening a second
pool, but owns its own tables entirely (np_categories, np_brands,
np_subcategories, np_sub_subcategories, np_products, np_orders,
np_order_items). The one exception is a small, backward-compatible migration
on the existing `tickets` table (two new nullable columns) so a ticket raised
from a Nykaa Pulse order shows up in the existing Admin/Team ticket queues
unchanged — see init_nykaa_db().

Same shape as store.py throughout: a `_XXX_SCHEMA` constant per table,
registered in init_nykaa_db(); plain functions per operation using `_conn()`
with %s placeholders and RETURNING *; a `_row_to_dict`-style helper per row
type that json.loads()'s the JSON columns.
"""
import json

from .store import _conn, _existing_columns, _now

_NP_CATEGORIES_SCHEMA = """
    CREATE TABLE IF NOT EXISTS np_categories (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL UNIQUE
    )
"""

_NP_BRANDS_SCHEMA = """
    CREATE TABLE IF NOT EXISTS np_brands (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL UNIQUE
    )
"""

_NP_SUBCATEGORIES_SCHEMA = """
    CREATE TABLE IF NOT EXISTS np_subcategories (
        id SERIAL PRIMARY KEY,
        category_id INTEGER NOT NULL REFERENCES np_categories(id),
        name TEXT NOT NULL,
        UNIQUE (category_id, name)
    )
"""

_NP_SUB_SUBCATEGORIES_SCHEMA = """
    CREATE TABLE IF NOT EXISTS np_sub_subcategories (
        id SERIAL PRIMARY KEY,
        subcategory_id INTEGER NOT NULL REFERENCES np_subcategories(id),
        name TEXT NOT NULL,
        UNIQUE (subcategory_id, name)
    )
"""

# details_json holds category-specific attributes (shade, finish, size,
# skin type, etc.) — a jsonb blob rather than a wide sparse table, since the
# relevant fields vary a lot by category (a lipstick's "shade" has no
# equivalent on a hair dryer). positive/negative_themes are the seed
# vocabulary feedback_ai's CATEGORY_THEMES was partly built from.
_NP_PRODUCTS_SCHEMA = """
    CREATE TABLE IF NOT EXISTS np_products (
        id SERIAL PRIMARY KEY,
        category_id INTEGER NOT NULL REFERENCES np_categories(id),
        brand_id INTEGER NOT NULL REFERENCES np_brands(id),
        subcategory_id INTEGER NOT NULL REFERENCES np_subcategories(id),
        sub_subcategory_id INTEGER NOT NULL REFERENCES np_sub_subcategories(id),
        name TEXT NOT NULL,
        description TEXT NOT NULL,
        price_inr NUMERIC NOT NULL,
        details_json TEXT NOT NULL,
        positive_themes_json TEXT NOT NULL,
        negative_themes_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
"""

# delivery_rating/compliment live on the order (one shipment-level rating),
# not per item — mirrors the real Nykaa teardown's "delivery rating is a
# separate, order-level ask" finding.
_NP_ORDERS_SCHEMA = """
    CREATE TABLE IF NOT EXISTS np_orders (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'Delivered',
        placed_at TEXT NOT NULL,
        delivered_at TEXT,
        total_amount NUMERIC NOT NULL,
        delivery_rating INTEGER,
        delivery_compliment TEXT
    )
"""

# rating/review_title/review_description are each independently nullable —
# deliberately not forced together as a group, unlike real Nykaa's mandatory
# title+description (see the teardown's "rigid review format" finding).
_NP_ORDER_ITEMS_SCHEMA = """
    CREATE TABLE IF NOT EXISTS np_order_items (
        id SERIAL PRIMARY KEY,
        order_id INTEGER NOT NULL REFERENCES np_orders(id),
        product_id INTEGER NOT NULL REFERENCES np_products(id),
        quantity INTEGER NOT NULL,
        unit_price_at_purchase NUMERIC NOT NULL,
        rating INTEGER,
        review_title TEXT,
        review_description TEXT,
        review_status TEXT NOT NULL DEFAULT 'none',
        created_at TEXT NOT NULL
    )
"""

# Nykaa's own clearest differentiator per the teardown research: a
# once-declared profile shown alongside a customer's reviews so another
# shopper can read "someone with my skin type liked this" — and, on the PM
# side, lets the fit summarizer segment ratings/sentiment by attribute
# instead of just averaging everyone together. One row per user, current
# state only (no history) — a review shows whatever the reviewer's profile
# says *now*, not what it said when they wrote it, same as how a "verified
# purchaser" badge is normally live-state rather than a snapshot.
_NP_BEAUTY_PROFILES_SCHEMA = """
    CREATE TABLE IF NOT EXISTS np_beauty_profiles (
        user_id INTEGER PRIMARY KEY,
        skin_type TEXT,
        skin_concerns_json TEXT,
        date_of_birth TEXT,
        hair_type TEXT,
        scalp_type TEXT,
        hair_concerns_json TEXT,
        skin_tone TEXT,
        undertone TEXT,
        makeup_preferences TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
"""

# ---- Nykaa Pulse's own chat/ticket/feedback tables ---------------------------
# Deliberately separate from the shared tickets/ticket_comments/feedback_items
# tables the rest of the app ("My Existing Project"/Mission tab) uses — only
# `users` stays shared. Mirrors store.py's shape (same columns/lifecycle)
# throughout, just scoped to np_orders/np_order_items instead of freeform.

# Pre-escalation scratch space — a customer chats with the bot here before any
# ticket exists. One active conversation per order item.
_NP_CHAT_TURNS_SCHEMA = """
    CREATE TABLE IF NOT EXISTS np_chat_turns (
        id SERIAL PRIMARY KEY,
        order_id INTEGER NOT NULL REFERENCES np_orders(id),
        item_id INTEGER NOT NULL REFERENCES np_order_items(id),
        role TEXT NOT NULL,
        text TEXT NOT NULL,
        created_at TEXT NOT NULL,
        attachment_data BYTEA,
        attachment_name TEXT,
        attachment_mime TEXT
    )
"""

# Unlike the shared tickets table, a np_ticket only ever comes into existence
# already classified — it's created at the moment of escalation, when a
# category/team/priority is already in hand (from a hard-trigger or from
# run_chat_turn's own escalate decision), so there's no unrouted 'New' state.
_NP_TICKETS_SCHEMA = """
    CREATE TABLE IF NOT EXISTS np_tickets (
        id SERIAL PRIMARY KEY,
        order_id INTEGER NOT NULL REFERENCES np_orders(id),
        item_id INTEGER NOT NULL REFERENCES np_order_items(id),
        user_id INTEGER NOT NULL,
        message TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Routed',
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
        created_at TEXT NOT NULL
    )
"""

# author_role is 'user' | 'bot' | 'team' | 'admin' — the bot-phase transcript
# is bulk-copied in here at escalation time (author_role='bot'/'user'), then
# live human replies continue the same thread (author_role='team'/'admin').
_NP_TICKET_COMMENTS_SCHEMA = """
    CREATE TABLE IF NOT EXISTS np_ticket_comments (
        id SERIAL PRIMARY KEY,
        np_ticket_id INTEGER NOT NULL REFERENCES np_tickets(id),
        author_role TEXT NOT NULL,
        author_name TEXT NOT NULL,
        body TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
"""

_NP_TICKET_COMMENT_READS_SCHEMA = """
    CREATE TABLE IF NOT EXISTS np_ticket_comment_reads (
        np_ticket_id INTEGER NOT NULL,
        viewer_role TEXT NOT NULL,
        viewer_key TEXT NOT NULL,
        last_read_at TEXT NOT NULL,
        PRIMARY KEY (np_ticket_id, viewer_role, viewer_key)
    )
"""

# Nykaa Pulse's own copy of the sentiment/category/urgency log the PM
# analytics (nykaa_insights.py) reads — replaces the shared feedback_items
# table as this app's review/ticket-text analysis destination.
_NP_FEEDBACK_ITEMS_SCHEMA = """
    CREATE TABLE IF NOT EXISTS np_feedback_items (
        id SERIAL PRIMARY KEY,
        source_type TEXT NOT NULL,
        source_ref INTEGER,
        user_id INTEGER,
        rating INTEGER,
        text TEXT NOT NULL,
        sentiment_label TEXT,
        sentiment_score REAL,
        category TEXT,
        theme TEXT,
        urgency_score REAL,
        is_actionable_ticket INTEGER,
        model_used TEXT,
        mode TEXT,
        latency_ms INTEGER,
        created_at TEXT NOT NULL
    )
"""

# One persisted brand-insight report per (period_type, period_key) — same
# "generate once, reread after" shape as the Mission side's periodic_insights
# table, but auto-populated on first GET rather than requiring an explicit
# "Generate" click (see nykaa_insights.generate_brand_report), and storing
# the whole {report, mode, model_used, trend} response as one JSON blob
# since nothing here needs to query into its fields server-side. UNIQUE
# makes re-saving the still-open current period an upsert, not a growing
# pile of rows.
_NP_PERIODIC_REPORTS_SCHEMA = """
    CREATE TABLE IF NOT EXISTS np_periodic_reports (
        id SERIAL PRIMARY KEY,
        period_type TEXT NOT NULL,
        period_key TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        generated_at TEXT NOT NULL,
        UNIQUE (period_type, period_key)
    )
"""

# App/website feedback — a star rating plus what went wrong, about the shop
# itself (a broken button, a slow page) rather than about any product. Real
# Nykaa has no such channel; the floating widget in the corner of the shop
# is this app's answer to that gap. Deliberately its own table rather than
# another np_feedback_items row: there's no order/product/brand behind it
# to join against, so it doesn't belong in the review-analytics pipeline.
_NP_APP_FEEDBACK_SCHEMA = """
    CREATE TABLE IF NOT EXISTS np_app_feedback (
        id SERIAL PRIMARY KEY,
        user_id INTEGER,
        rating INTEGER NOT NULL,
        category TEXT NOT NULL,
        description TEXT,
        created_at TEXT NOT NULL
    )
"""

# `category` was originally one fixed label per submission — the widget now
# lets a customer pick more than one, so a new `categories_json` column
# holds the full list (JSON array), with `category` kept as a comma-joined
# display string for anything still reading the old column directly.


def init_nykaa_db() -> None:
    with _conn() as conn:
        conn.execute(_NP_CATEGORIES_SCHEMA)
        conn.execute(_NP_BRANDS_SCHEMA)
        conn.execute(_NP_SUBCATEGORIES_SCHEMA)
        conn.execute(_NP_SUB_SUBCATEGORIES_SCHEMA)
        conn.execute(_NP_PRODUCTS_SCHEMA)
        conn.execute(_NP_ORDERS_SCHEMA)
        conn.execute(_NP_ORDER_ITEMS_SCHEMA)
        conn.execute(_NP_BEAUTY_PROFILES_SCHEMA)
        conn.execute(_NP_CHAT_TURNS_SCHEMA)
        conn.execute(_NP_TICKETS_SCHEMA)
        conn.execute(_NP_TICKET_COMMENTS_SCHEMA)
        conn.execute(_NP_TICKET_COMMENT_READS_SCHEMA)
        conn.execute(_NP_FEEDBACK_ITEMS_SCHEMA)
        conn.execute(_NP_PERIODIC_REPORTS_SCHEMA)
        conn.execute(_NP_APP_FEEDBACK_SCHEMA)

        # Additive, nullable-only migration on the existing tickets table —
        # a ticket raised from a Nykaa Pulse order is tagged with which
        # order/product it's about, but every pre-existing ticket (and every
        # ticket raised outside Nykaa Pulse) is completely unaffected.
        ticket_cols = _existing_columns(conn, "tickets")
        if "np_order_id" not in ticket_cols:
            conn.execute("ALTER TABLE tickets ADD COLUMN np_order_id INTEGER")
        if "np_product_id" not in ticket_cols:
            conn.execute("ALTER TABLE tickets ADD COLUMN np_product_id INTEGER")

        # Phase 2: optional review photo ("Show off your look!") and a
        # link back to whichever ticket this item is associated with —
        # either raised manually or auto-opened by the review-to-ticket
        # linking below. Nullable-only, added after np_order_items already
        # existed in some databases (mirrors the tickets migration above).
        item_cols = _existing_columns(conn, "np_order_items")
        if "review_photo_data" not in item_cols:
            conn.execute("ALTER TABLE np_order_items ADD COLUMN review_photo_data BYTEA")
        if "review_photo_name" not in item_cols:
            conn.execute("ALTER TABLE np_order_items ADD COLUMN review_photo_name TEXT")
        if "review_photo_mime" not in item_cols:
            conn.execute("ALTER TABLE np_order_items ADD COLUMN review_photo_mime TEXT")
        if "linked_ticket_id" not in item_cols:
            conn.execute("ALTER TABLE np_order_items ADD COLUMN linked_ticket_id INTEGER")

        # `summary` — a short AI-written title for the ticket's issue (see
        # nykaa_ai_features.summarize_ticket_issue), shown in the Admin
        # ticket table instead of the raw transcript. `csat_rating`/
        # `csat_comment` — the customer's 1-5 rating of the support
        # experience, asked for once a ticket is Resolved.
        app_feedback_cols = _existing_columns(conn, "np_app_feedback")
        if "categories_json" not in app_feedback_cols:
            conn.execute("ALTER TABLE np_app_feedback ADD COLUMN categories_json TEXT")

        np_ticket_cols = _existing_columns(conn, "np_tickets")
        if "summary" not in np_ticket_cols:
            conn.execute("ALTER TABLE np_tickets ADD COLUMN summary TEXT")
        if "csat_rating" not in np_ticket_cols:
            conn.execute("ALTER TABLE np_tickets ADD COLUMN csat_rating INTEGER")
        if "csat_comment" not in np_ticket_cols:
            conn.execute("ALTER TABLE np_tickets ADD COLUMN csat_comment TEXT")

        # Beauty Portfolio grew from 3 freeform fields into the accordion-quiz
        # shape (skin concerns, DOB, scalp type, hair concerns, skin
        # tone/undertone) — additive, nullable-only, same guarded pattern.
        bp_cols = _existing_columns(conn, "np_beauty_profiles")
        if "skin_concerns_json" not in bp_cols:
            conn.execute("ALTER TABLE np_beauty_profiles ADD COLUMN skin_concerns_json TEXT")
        if "date_of_birth" not in bp_cols:
            conn.execute("ALTER TABLE np_beauty_profiles ADD COLUMN date_of_birth TEXT")
        if "scalp_type" not in bp_cols:
            conn.execute("ALTER TABLE np_beauty_profiles ADD COLUMN scalp_type TEXT")
        if "hair_concerns_json" not in bp_cols:
            conn.execute("ALTER TABLE np_beauty_profiles ADD COLUMN hair_concerns_json TEXT")
        if "skin_tone" not in bp_cols:
            conn.execute("ALTER TABLE np_beauty_profiles ADD COLUMN skin_tone TEXT")
        if "undertone" not in bp_cols:
            conn.execute("ALTER TABLE np_beauty_profiles ADD COLUMN undertone TEXT")

        # Attachment support — same in-place nullable-column pattern as the
        # shared ticket_comments table (see store.py's own migration): a
        # customer or team member can attach a file instead of (or with) a
        # text body.
        np_comment_cols = _existing_columns(conn, "np_ticket_comments")
        for col in ("attachment_name", "attachment_mime"):
            if col not in np_comment_cols:
                conn.execute(f"ALTER TABLE np_ticket_comments ADD COLUMN {col} TEXT")
        if "attachment_data" not in np_comment_cols:
            conn.execute("ALTER TABLE np_ticket_comments ADD COLUMN attachment_data BYTEA")

        # Same attachment support, extended to the pre-escalation bot-phase
        # chat (np_chat_turns) — lets a customer attach a file before a
        # ticket even exists yet, not just after a human has picked it up.
        np_chat_turn_cols = _existing_columns(conn, "np_chat_turns")
        for col in ("attachment_name", "attachment_mime"):
            if col not in np_chat_turn_cols:
                conn.execute(f"ALTER TABLE np_chat_turns ADD COLUMN {col} TEXT")
        if "attachment_data" not in np_chat_turn_cols:
            conn.execute("ALTER TABLE np_chat_turns ADD COLUMN attachment_data BYTEA")


# ---- catalog: seed-time inserts --------------------------------------------

def insert_category(name: str) -> int:
    with _conn() as conn:
        return conn.execute(
            "INSERT INTO np_categories (name) VALUES (%s) ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name RETURNING id",
            (name,),
        ).fetchone()["id"]


def insert_brand(name: str) -> int:
    with _conn() as conn:
        return conn.execute(
            "INSERT INTO np_brands (name) VALUES (%s) ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name RETURNING id",
            (name,),
        ).fetchone()["id"]


def insert_subcategory(category_id: int, name: str) -> int:
    with _conn() as conn:
        return conn.execute(
            """INSERT INTO np_subcategories (category_id, name) VALUES (%s, %s)
               ON CONFLICT (category_id, name) DO UPDATE SET name = EXCLUDED.name RETURNING id""",
            (category_id, name),
        ).fetchone()["id"]


def insert_sub_subcategory(subcategory_id: int, name: str) -> int:
    with _conn() as conn:
        return conn.execute(
            """INSERT INTO np_sub_subcategories (subcategory_id, name) VALUES (%s, %s)
               ON CONFLICT (subcategory_id, name) DO UPDATE SET name = EXCLUDED.name RETURNING id""",
            (subcategory_id, name),
        ).fetchone()["id"]


def insert_product(
    category_id: int, brand_id: int, subcategory_id: int, sub_subcategory_id: int,
    name: str, description: str, price_inr: float, details: dict,
    positive_themes: list[str], negative_themes: list[str],
) -> int:
    with _conn() as conn:
        return conn.execute(
            """INSERT INTO np_products (
                category_id, brand_id, subcategory_id, sub_subcategory_id, name, description,
                price_inr, details_json, positive_themes_json, negative_themes_json, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (
                category_id, brand_id, subcategory_id, sub_subcategory_id, name, description,
                price_inr, json.dumps(details), json.dumps(positive_themes), json.dumps(negative_themes), _now(),
            ),
        ).fetchone()["id"]


def catalog_is_seeded() -> bool:
    with _conn() as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM np_categories").fetchone()
        return row["n"] > 0


# ---- catalog: reads ---------------------------------------------------------

def list_categories() -> list[dict]:
    with _conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM np_categories ORDER BY name").fetchall()]


def list_brands(category_id: int | None = None) -> list[dict]:
    """Every brand, or — when given — only brands with at least one product
    in that category, so the catalog's brand filter can narrow to what's
    actually selectable once a category is picked."""
    with _conn() as conn:
        if category_id is not None:
            rows = conn.execute(
                """SELECT DISTINCT b.* FROM np_brands b
                   JOIN np_products p ON p.brand_id = b.id
                   WHERE p.category_id = %s ORDER BY b.name""",
                (category_id,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM np_brands ORDER BY name").fetchall()
        return [dict(r) for r in rows]


def list_subcategories(category_id: int | None = None) -> list[dict]:
    with _conn() as conn:
        if category_id is not None:
            rows = conn.execute(
                "SELECT * FROM np_subcategories WHERE category_id = %s ORDER BY name", (category_id,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM np_subcategories ORDER BY name").fetchall()
        return [dict(r) for r in rows]


_PRODUCT_LIST_SQL = """
    SELECT p.id, p.name, p.description, p.price_inr, p.details_json,
           p.positive_themes_json, p.negative_themes_json,
           c.id AS category_id, c.name AS category_name,
           b.id AS brand_id, b.name AS brand_name,
           sc.id AS subcategory_id, sc.name AS subcategory_name,
           ssc.id AS sub_subcategory_id, ssc.name AS sub_subcategory_name
    FROM np_products p
    JOIN np_categories c ON c.id = p.category_id
    JOIN np_brands b ON b.id = p.brand_id
    JOIN np_subcategories sc ON sc.id = p.subcategory_id
    JOIN np_sub_subcategories ssc ON ssc.id = p.sub_subcategory_id
"""


def _product_row_to_dict(row: dict) -> dict:
    d = dict(row)
    d["details"] = json.loads(d.pop("details_json"))
    d["positive_themes"] = json.loads(d.pop("positive_themes_json"))
    d["negative_themes"] = json.loads(d.pop("negative_themes_json"))
    return d


def list_products(category_id: int | None = None, brand_id: int | None = None,
                   subcategory_id: int | None = None, search: str | None = None) -> list[dict]:
    clauses, params = [], []
    if category_id is not None:
        clauses.append("p.category_id = %s")
        params.append(category_id)
    if brand_id is not None:
        clauses.append("p.brand_id = %s")
        params.append(brand_id)
    if subcategory_id is not None:
        clauses.append("p.subcategory_id = %s")
        params.append(subcategory_id)
    if search:
        clauses.append("p.name ILIKE %s")
        params.append(f"%{search}%")
    sql = _PRODUCT_LIST_SQL
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY p.name"
    with _conn() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [_product_row_to_dict(r) for r in rows]


def get_product(product_id: int) -> dict | None:
    with _conn() as conn:
        row = conn.execute(_PRODUCT_LIST_SQL + " WHERE p.id = %s", (product_id,)).fetchone()
        return _product_row_to_dict(row) if row else None


_AVG_RATING_ORDER = """
    ORDER BY (SELECT AVG(oi.rating) FROM np_order_items oi WHERE oi.product_id = p.id AND oi.rating IS NOT NULL) DESC NULLS LAST
    LIMIT %s
"""


_RECOMMENDATION_SECTIONS = {
    # section -> (category name, details_json field to match against, profile keys for [type, concerns])
    "skin": ("Skincare", "skin_type", "skin_type", "skin_concerns"),
    "hair": ("Hair Care", "hair_type", "hair_type", "hair_concerns"),
    # Makeup products don't carry a structured skin_tone/undertone field —
    # only a free-text `shade` (e.g. "128 Warm Nude") — so undertone is
    # matched loosely against shade text instead, the way real shade names
    # often do encode it; still a real, non-fabricated signal, just weaker.
    "makeup": ("Makeup", "shade", None, "undertone"),
}


def list_recommended_products(section: str, profile: dict, limit: int = 8) -> list[dict]:
    """Products matching the customer's saved Beauty Portfolio for one
    section (skin/hair/makeup), ranked by average customer rating; falls
    back to that section's top-rated products when nothing matches yet
    (e.g. an empty profile, or a type no seeded product happens to
    mention)."""
    category_name, details_field, type_key, concerns_key = _RECOMMENDATION_SECTIONS[section]
    type_value = profile.get(type_key) if type_key else None
    concerns = profile.get(concerns_key) if concerns_key else None
    if isinstance(concerns, str):
        concerns = [concerns]

    with _conn() as conn:
        rows = []
        clauses, params = [], []
        if type_value:
            clauses.append(f"p.details_json::jsonb ->> '{details_field}' = %s")
            params.append(type_value)
        for concern in concerns or []:
            clauses.append(f"p.details_json::jsonb ->> '{details_field}' ILIKE %s")
            params.append(f"%{concern}%")
        if clauses:
            sql = _PRODUCT_LIST_SQL + " WHERE c.name = %s AND (" + " OR ".join(clauses) + ")" + _AVG_RATING_ORDER
            rows = conn.execute(sql, (category_name, *params, limit)).fetchall()
        if not rows:
            sql = _PRODUCT_LIST_SQL + " WHERE c.name = %s" + _AVG_RATING_ORDER
            rows = conn.execute(sql, (category_name, limit)).fetchall()
        return [_product_row_to_dict(r) for r in rows]


# Canonical routine steps — each maps 1:1 onto one of Skincare/Hair Care's
# own seeded subcategories, so every step always has real products to
# choose from regardless of anyone's review history (unlike
# compute_product_rollup, which only sees already-reviewed products).
_SKINCARE_ROUTINE_STEPS = [("Cleanser", "Cleansers"), ("Serum", "Serums"), ("Moisturizer", "Moisturizers"), ("Sunscreen", "Sunscreens")]
_HAIRCARE_ROUTINE_STEPS = [("Shampoo", "Shampoo"), ("Conditioner", "Conditioner"), ("Hair Oil", "Hair Oil"), ("Styling", "Hair Styling")]


def list_routine_step_candidates(
    category_name: str, subcategory_name: str, type_field: str, type_value: str | None,
    concerns: list[str] | None = None, limit: int = 3,
) -> list[dict]:
    """Every product is eligible (not just reviewed ones) — ranked so an
    exact type match beats a concern-keyword match beats plain popularity.
    `matched_on` records which of those actually applied, for the
    fallback's reason text."""
    with _conn() as conn:
        params = []
        if type_value:
            type_match_sql = "(p.details_json::jsonb ->> %s = %s)"
            params += [type_field, type_value]
        else:
            type_match_sql = "false"

        concern_terms = []
        for c in concerns or []:
            concern_terms.append("(p.details_json::jsonb ->> %s ILIKE %s)")
            params += [type_field, f"%{c}%"]
        concern_match_sql = " OR ".join(concern_terms) if concern_terms else "false"

        params += [category_name, subcategory_name, limit]

        rows = conn.execute(f"""
            SELECT p.id, p.name, b.name AS brand_name,
                   {type_match_sql} AS type_match,
                   ({concern_match_sql}) AS concern_match,
                   (SELECT AVG(oi.rating) FROM np_order_items oi WHERE oi.product_id = p.id AND oi.rating IS NOT NULL) AS avg_rating
            FROM np_products p
            JOIN np_brands b ON b.id = p.brand_id
            JOIN np_categories c ON c.id = p.category_id
            JOIN np_subcategories sc ON sc.id = p.subcategory_id
            WHERE c.name = %s AND sc.name = %s
            ORDER BY type_match DESC, concern_match DESC, avg_rating DESC NULLS LAST
            LIMIT %s
        """, params).fetchall()
        return [
            {
                "product_id": r["id"], "product_name": r["name"], "brand": r["brand_name"],
                "avg_rating": round(float(r["avg_rating"]), 2) if r["avg_rating"] is not None else None,
                "matched_on": "type" if r["type_match"] else ("concern" if r["concern_match"] else "popularity"),
            }
            for r in rows
        ]


def compute_routine_candidates(profile: dict) -> dict:
    """{"skincare": [{"step": "Cleanser", "candidates": [...]}, ...], "haircare": [...]} —
    the input nykaa_ai_features.generate_beauty_routine picks from."""
    return {
        "skincare": [
            {"step": step, "candidates": list_routine_step_candidates(
                "Skincare", subcat, "skin_type", profile.get("skin_type"), profile.get("skin_concerns"),
            )}
            for step, subcat in _SKINCARE_ROUTINE_STEPS
        ],
        "haircare": [
            {"step": step, "candidates": list_routine_step_candidates(
                "Hair Care", subcat, "hair_type", profile.get("hair_type"), profile.get("hair_concerns"),
            )}
            for step, subcat in _HAIRCARE_ROUTINE_STEPS
        ],
    }


def list_published_review_texts(product_id: int) -> list[str]:
    """Title + description of every *published* (moderator-approved) review
    for one product — the corpus the Phase 4 fit-summarizer and
    ask-the-reviews features are grounded in. Deliberately excludes
    pending/rejected reviews, same trust gate real Nykaa applies before a
    review is shown to other shoppers."""
    with _conn() as conn:
        rows = conn.execute(
            """SELECT review_title, review_description FROM np_order_items
               WHERE product_id = %s AND review_status = 'published'
                 AND (review_title IS NOT NULL OR review_description IS NOT NULL)""",
            (product_id,),
        ).fetchall()
        texts = []
        for r in rows:
            parts = [p for p in (r["review_title"], r["review_description"]) if p and p.strip()]
            if parts:
                texts.append(" — ".join(parts))
        return texts


def list_published_reviews_with_profile(product_id: int) -> list[dict]:
    """Every published review for one product, each with the reviewer's
    *current* Beauty Portfolio attributes (nullable — most reviewers may not
    have set one up) — this is what makes a review read as "someone with my
    skin type liked this" instead of an anonymous star rating, and what lets
    the fit summarizer segment by attribute rather than average everyone
    together."""
    with _conn() as conn:
        rows = conn.execute(
            """SELECT oi.id, oi.rating, oi.review_title, oi.review_description, oi.created_at,
                      (oi.review_photo_data IS NOT NULL) AS has_photo,
                      bp.skin_type, bp.hair_type
               FROM np_order_items oi
               JOIN np_orders o ON o.id = oi.order_id
               LEFT JOIN np_beauty_profiles bp ON bp.user_id = o.user_id
               WHERE oi.product_id = %s AND oi.review_status = 'published'
                 AND (oi.review_title IS NOT NULL OR oi.review_description IS NOT NULL OR oi.rating IS NOT NULL)
               ORDER BY oi.created_at DESC""",
            (product_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def upsert_beauty_profile(
    user_id: int, skin_type: str | None, hair_type: str | None, makeup_preferences: str | None,
    skin_concerns: list[str] | None = None, date_of_birth: str | None = None, scalp_type: str | None = None,
    hair_concerns: list[str] | None = None, skin_tone: str | None = None, undertone: str | None = None,
) -> dict:
    with _conn() as conn:
        row = conn.execute(
            """INSERT INTO np_beauty_profiles (
                   user_id, skin_type, skin_concerns_json, date_of_birth, hair_type, scalp_type,
                   hair_concerns_json, skin_tone, undertone, makeup_preferences, created_at, updated_at
               )
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (user_id) DO UPDATE SET
                   skin_type = EXCLUDED.skin_type, skin_concerns_json = EXCLUDED.skin_concerns_json,
                   date_of_birth = EXCLUDED.date_of_birth, hair_type = EXCLUDED.hair_type,
                   scalp_type = EXCLUDED.scalp_type, hair_concerns_json = EXCLUDED.hair_concerns_json,
                   skin_tone = EXCLUDED.skin_tone, undertone = EXCLUDED.undertone,
                   makeup_preferences = EXCLUDED.makeup_preferences, updated_at = EXCLUDED.updated_at
               RETURNING *""",
            (
                user_id, skin_type, json.dumps(skin_concerns) if skin_concerns else None, date_of_birth,
                hair_type, scalp_type, json.dumps(hair_concerns) if hair_concerns else None,
                skin_tone, undertone, makeup_preferences, _now(), _now(),
            ),
        ).fetchone()
        return _beauty_profile_row_to_dict(dict(row))


def get_beauty_profile(user_id: int) -> dict | None:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM np_beauty_profiles WHERE user_id = %s", (user_id,)).fetchone()
        return _beauty_profile_row_to_dict(dict(row)) if row else None


def _beauty_profile_row_to_dict(row: dict) -> dict:
    skin_concerns_json = row.pop("skin_concerns_json", None)
    hair_concerns_json = row.pop("hair_concerns_json", None)
    row["skin_concerns"] = json.loads(skin_concerns_json) if skin_concerns_json else []
    row["hair_concerns"] = json.loads(hair_concerns_json) if hair_concerns_json else []
    return row


# ---- orders -----------------------------------------------------------------

def create_order(user_id: int, items: list[dict]) -> dict:
    """items: [{"product_id": int, "quantity": int}, ...]. Prices are read
    server-side from the catalog at order time — never trusted from the
    client — and frozen onto each order_item as unit_price_at_purchase."""
    with _conn() as conn:
        total = 0.0
        line_items = []
        for item in items:
            product = conn.execute("SELECT price_inr FROM np_products WHERE id = %s", (item["product_id"],)).fetchone()
            if not product:
                continue
            unit_price = float(product["price_inr"])
            total += unit_price * item["quantity"]
            line_items.append((item["product_id"], item["quantity"], unit_price))

        order_row = conn.execute(
            "INSERT INTO np_orders (user_id, status, placed_at, total_amount) VALUES (%s, 'Delivered', %s, %s) RETURNING *",
            (user_id, _now(), total),
        ).fetchone()

        for product_id, quantity, unit_price in line_items:
            conn.execute(
                """INSERT INTO np_order_items (order_id, product_id, quantity, unit_price_at_purchase, review_status, created_at)
                   VALUES (%s, %s, %s, %s, 'none', %s)""",
                (order_row["id"], product_id, quantity, unit_price, _now()),
            )
        # Reuse this same connection/transaction rather than calling
        # get_order() (which would open a second pooled connection and try
        # to read these rows before this transaction has committed).
        return _order_with_items(conn, order_row)


# Explicit column list everywhere order items are read for a JSON response —
# deliberately excludes review_photo_data (BYTEA): psycopg would hand back
# raw bytes, which FastAPI can't JSON-encode, and no list/detail view needs
# the actual image anyway (the two dedicated photo endpoints below are the
# only places that select it). has_photo is a cheap boolean stand-in.
_ORDER_ITEM_COLUMNS = """
    oi.id, oi.order_id, oi.product_id, oi.quantity, oi.unit_price_at_purchase,
    oi.rating, oi.review_title, oi.review_description, oi.review_status,
    oi.created_at, oi.linked_ticket_id, (oi.review_photo_data IS NOT NULL) AS has_photo
"""

_ORDER_ITEMS_SQL = f"""
    SELECT {_ORDER_ITEM_COLUMNS}, p.name AS product_name, p.description AS product_description,
           t.status AS ticket_status
    FROM np_order_items oi
    JOIN np_products p ON p.id = oi.product_id
    LEFT JOIN np_tickets t ON t.id = oi.linked_ticket_id
    WHERE oi.order_id = %s
    ORDER BY oi.id
"""


def _order_with_items(conn, order_row: dict) -> dict:
    order = dict(order_row)
    items = conn.execute(_ORDER_ITEMS_SQL, (order["id"],)).fetchall()
    order["items"] = [dict(i) for i in items]
    return order


def _merge_unread_counts(orders: list[dict], user_id: int) -> list[dict]:
    """Batch-computes unread-reply counts once across every linked ticket in
    these orders (not per-order — this is a post-processing step, not part
    of _order_with_items, specifically so a user with many orders doesn't
    open one extra pooled connection per order). Powers the customer-facing
    chat icon's red badge, same unread_np_comment_counts already used for
    Team's own badge — just called with viewer_role="user" this time."""
    ticket_ids = [i["linked_ticket_id"] for o in orders for i in o["items"] if i.get("linked_ticket_id")]
    if not ticket_ids:
        return orders
    unread = unread_np_comment_counts(ticket_ids, "user", str(user_id))
    for o in orders:
        for i in o["items"]:
            i["unread_comments"] = unread.get(i["linked_ticket_id"], 0) if i.get("linked_ticket_id") else 0
    return orders


def get_order(order_id: int) -> dict | None:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM np_orders WHERE id = %s", (order_id,)).fetchone()
        if not row:
            return None
        order = _order_with_items(conn, row)
    return _merge_unread_counts([order], order["user_id"])[0]


def list_orders_for_user(user_id: int) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM np_orders WHERE user_id = %s ORDER BY id DESC", (user_id,)).fetchall()
        orders = [_order_with_items(conn, r) for r in rows]
    return _merge_unread_counts(orders, user_id)


def list_all_orders() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM np_orders ORDER BY id DESC").fetchall()
        return [_order_with_items(conn, r) for r in rows]


def _get_order_item(conn, item_id: int) -> dict | None:
    row = conn.execute(f"SELECT {_ORDER_ITEM_COLUMNS} FROM np_order_items oi WHERE oi.id = %s", (item_id,)).fetchone()
    return dict(row) if row else None


def submit_item_review(order_id: int, item_id: int, rating: int | None, title: str | None, description: str | None) -> dict | None:
    """rating/title/description are each independently optional — a customer
    can submit just a star rating, just a note, or all of it. Publishes
    immediately — there's no moderation gate (removed: escalation to a real
    person already happens automatically via the chat, so a human review
    queue for star ratings/text wasn't adding anything)."""
    with _conn() as conn:
        updated = conn.execute(
            """UPDATE np_order_items SET rating = %s, review_title = %s, review_description = %s,
               review_status = 'published'
               WHERE id = %s AND order_id = %s RETURNING id""",
            (rating, title, description, item_id, order_id),
        ).fetchone()
        return _get_order_item(conn, item_id) if updated else None


def save_review_photo(order_id: int, item_id: int, data: bytes, name: str, mime: str) -> bool:
    """"Show off your look!" — an optional photo attached to a review, same
    upload as the rest of the review but its own endpoint (multipart, not
    JSON). Returns False if the item doesn't belong to this order."""
    with _conn() as conn:
        row = conn.execute(
            """UPDATE np_order_items SET review_photo_data = %s, review_photo_name = %s, review_photo_mime = %s
               WHERE id = %s AND order_id = %s RETURNING id""",
            (data, name, mime, item_id, order_id),
        ).fetchone()
        return row is not None


def get_review_photo(item_id: int) -> dict | None:
    """Returns {order_id, data, name, mime} for the caller to enforce access
    (own order, or admin) before handing back the raw bytes."""
    with _conn() as conn:
        row = conn.execute(
            """SELECT order_id, review_photo_data AS data, review_photo_name AS name, review_photo_mime AS mime
               FROM np_order_items WHERE id = %s""",
            (item_id,),
        ).fetchone()
        return dict(row) if row and row["data"] else None


def submit_delivery_rating(order_id: int, rating: int, compliment: str | None) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "UPDATE np_orders SET delivery_rating = %s, delivery_compliment = %s WHERE id = %s RETURNING *",
            (rating, compliment, order_id),
        ).fetchone()
        return dict(row) if row else None


def set_linked_ticket(item_id: int, ticket_id: int) -> None:
    """Idempotency guard for review-to-ticket auto-linking: recorded the
    moment a ticket is created for an item (whether auto-opened from an
    actionable review or manually raised), so the same item never spawns a
    second ticket. ticket_id refers to np_tickets.id."""
    with _conn() as conn:
        conn.execute("UPDATE np_order_items SET linked_ticket_id = %s WHERE id = %s", (ticket_id, item_id))


# ---- chat turns (pre-escalation scratch space) -------------------------------

# Every JSON-facing read excludes attachment_data (raw bytes aren't
# JSON-serializable) — same split as np_ticket_comments'
# _NP_COMMENT_JSON_COLUMNS/list_np_ticket_comments_with_attachments below.
_NP_CHAT_TURN_JSON_COLUMNS = "id, order_id, item_id, role, text, created_at, attachment_name, attachment_mime"


def add_chat_turn(
    order_id: int, item_id: int, role: str, text: str,
    attachment_data: bytes | None = None, attachment_name: str | None = None, attachment_mime: str | None = None,
) -> dict:
    with _conn() as conn:
        row = conn.execute(
            f"""INSERT INTO np_chat_turns (order_id, item_id, role, text, created_at, attachment_data, attachment_name, attachment_mime)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING {_NP_CHAT_TURN_JSON_COLUMNS}""",
            (order_id, item_id, role, text, _now(), attachment_data, attachment_name, attachment_mime),
        ).fetchone()
        return dict(row)


def list_chat_turns(order_id: int, item_id: int) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            f"SELECT {_NP_CHAT_TURN_JSON_COLUMNS} FROM np_chat_turns WHERE order_id = %s AND item_id = %s ORDER BY created_at ASC",
            (order_id, item_id),
        ).fetchall()
        return [dict(r) for r in rows]


def list_chat_turns_with_attachments(order_id: int, item_id: int) -> list[dict]:
    """Includes attachment_data — only for server-side use (chat_turn's own
    escalation bulk-copy into the ticket thread). Never JSON-serialize this;
    use list_chat_turns for anything API-facing."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM np_chat_turns WHERE order_id = %s AND item_id = %s ORDER BY created_at ASC",
            (order_id, item_id),
        ).fetchall()
        return [dict(r) for r in rows]


def get_chat_turn(turn_id: int) -> dict | None:
    """Includes attachment_data — only call this from the file-download
    endpoint, never anywhere the result gets JSON-serialized."""
    with _conn() as conn:
        row = conn.execute("SELECT * FROM np_chat_turns WHERE id = %s", (turn_id,)).fetchone()
        return dict(row) if row else None


# ---- Nykaa Pulse's own tickets ------------------------------------------------

def _np_ticket_row_to_dict(row: dict) -> dict:
    d = dict(row)
    d["is_ambiguous"] = bool(d["is_ambiguous"]) if d["is_ambiguous"] is not None else None
    d["escalated"] = bool(d["escalated"]) if d["escalated"] is not None else None
    return d


def create_np_ticket(order_id: int, item_id: int, user_id: int, message: str, result: dict, summary: str | None = None) -> dict:
    """Created already-classified (see _NP_TICKETS_SCHEMA's docstring) —
    `result` is a classifier.build_ticket_result()-shaped dict. `summary` is
    a short AI-written title (nykaa_ai_features.summarize_ticket_issue) —
    `message` stays the raw transcript for classification/audit."""
    with _conn() as conn:
        row = conn.execute(
            """INSERT INTO np_tickets (
                order_id, item_id, user_id, message, summary, status, category, priority, team, tone,
                confidence, is_ambiguous, escalated, reasoning, model_used, mode, latency_ms, created_at
            ) VALUES (%s, %s, %s, %s, %s, 'Routed', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *""",
            (
                order_id, item_id, user_id, message, summary, result["category"], result["priority"], result["team"],
                result["tone"], result["confidence"], int(result["is_ambiguous"]), int(result["escalated"]),
                result["reasoning"], result["model_used"], result["mode"], result["latency_ms"], _now(),
            ),
        ).fetchone()
        return _np_ticket_row_to_dict(row)


def update_np_ticket_summary(ticket_id: int, summary: str) -> None:
    """Backfills the AI-written title once it's ready — chat_turn creates the
    ticket immediately with an instant fallback title (see nykaa_ai_features.
    fallback_ticket_title) so the customer's escalation reply isn't blocked
    on a second LLM call, then schedules this as a background task."""
    with _conn() as conn:
        conn.execute("UPDATE np_tickets SET summary = %s WHERE id = %s", (summary, ticket_id))


def submit_np_ticket_csat(ticket_id: int, rating: int, comment: str | None) -> dict | None:
    """Only meaningful once Resolved and not yet rated — nykaa_routes.py
    enforces that gate; this just writes whatever it's given."""
    with _conn() as conn:
        row = conn.execute(
            "UPDATE np_tickets SET csat_rating = %s, csat_comment = %s WHERE id = %s RETURNING *",
            (rating, comment, ticket_id),
        ).fetchone()
        return _np_ticket_row_to_dict(row) if row else None


def get_np_ticket(ticket_id: int) -> dict | None:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM np_tickets WHERE id = %s", (ticket_id,)).fetchone()
        return _np_ticket_row_to_dict(row) if row else None


def list_ai_resolved_chats() -> list[dict]:
    """Every (order, item) conversation where the bot handled things without
    ever escalating to a ticket — the Nykaa Pulse mirror of store.py's
    list_self_resolved(), except this is a multi-turn transcript rather than
    a single suggest/confirm exchange. Invisible everywhere else, since a
    np_chat_turns row is only ever read back once np_tickets/np_ticket_
    comments exist. Grouped summary — call list_chat_turns(order_id, item_id)
    for the full transcript."""
    with _conn() as conn:
        rows = conn.execute("""
            SELECT oi.order_id, oi.id AS item_id, o.user_id, u.name AS user_name, u.email AS user_email,
                   p.name AS product_name, b.name AS brand,
                   COUNT(ct.id) AS turn_count,
                   MIN(ct.created_at) AS started_at,
                   MAX(ct.created_at) AS last_message_at,
                   (SELECT text FROM np_chat_turns
                    WHERE order_id = oi.order_id AND item_id = oi.id AND role = 'user'
                    ORDER BY created_at ASC LIMIT 1) AS first_message
            FROM np_chat_turns ct
            JOIN np_order_items oi ON oi.id = ct.item_id AND oi.order_id = ct.order_id
            JOIN np_orders o ON o.id = oi.order_id
            JOIN users u ON u.id = o.user_id
            JOIN np_products p ON p.id = oi.product_id
            JOIN np_brands b ON b.id = p.brand_id
            WHERE oi.linked_ticket_id IS NULL
            GROUP BY oi.order_id, oi.id, o.user_id, u.name, u.email, p.name, b.name
            ORDER BY MAX(ct.created_at) DESC
        """).fetchall()
        return [dict(r) for r in rows]


def get_np_ticket_with_user(ticket_id: int) -> dict | None:
    """Same as get_np_ticket, joined with the submitting user's name/email —
    same shape store.get_ticket_with_user gives the shared tickets table, so
    ticket_report.generate_ticket_report can be reused unchanged for a
    np_ticket's PDF export."""
    with _conn() as conn:
        row = conn.execute(
            """SELECT np_tickets.*, users.name AS user_name, users.email AS user_email
               FROM np_tickets JOIN users ON np_tickets.user_id = users.id
               WHERE np_tickets.id = %s""",
            (ticket_id,),
        ).fetchone()
        return _np_ticket_row_to_dict(row) if row else None


_NP_TICKET_LIST_SQL = """
    SELECT t.*, p.name AS product_name, b.name AS brand, u.name AS user_name, u.email AS user_email
    FROM np_tickets t
    JOIN np_order_items oi ON oi.id = t.item_id
    JOIN np_products p ON p.id = oi.product_id
    JOIN np_brands b ON b.id = p.brand_id
    JOIN users u ON u.id = t.user_id
"""


def list_np_tickets_for_team(team: str) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(_NP_TICKET_LIST_SQL + " WHERE t.team = %s ORDER BY t.id DESC", (team,)).fetchall()
        return [_np_ticket_row_to_dict(r) for r in rows]


def list_all_np_tickets() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(_NP_TICKET_LIST_SQL + " ORDER BY t.id DESC").fetchall()
        return [_np_ticket_row_to_dict(r) for r in rows]


def update_np_ticket_status(ticket_id: int, status: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "UPDATE np_tickets SET status = %s WHERE id = %s RETURNING *", (status, ticket_id)
        ).fetchone()
        return _np_ticket_row_to_dict(row) if row else None


# ---- Nykaa Pulse's own ticket comments ---------------------------------------

# Every JSON-facing read excludes attachment_data (raw bytes aren't
# JSON-serializable) — same split as the shared store.py's
# _COMMENT_JSON_COLUMNS/list_ticket_comments_with_attachments.
_NP_COMMENT_JSON_COLUMNS = "id, np_ticket_id, author_role, author_name, body, created_at, attachment_name, attachment_mime"


def add_np_ticket_comment(
    np_ticket_id: int,
    author_role: str,
    author_name: str,
    body: str,
    attachment_data: bytes | None = None,
    attachment_name: str | None = None,
    attachment_mime: str | None = None,
) -> dict:
    with _conn() as conn:
        row = conn.execute(
            f"""INSERT INTO np_ticket_comments
               (np_ticket_id, author_role, author_name, body, created_at, attachment_data, attachment_name, attachment_mime)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING {_NP_COMMENT_JSON_COLUMNS}""",
            (np_ticket_id, author_role, author_name, body, _now(), attachment_data, attachment_name, attachment_mime),
        ).fetchone()
        return dict(row)


def add_np_ticket_comments_bulk(np_ticket_id: int, rows: list[dict]) -> None:
    """Same insert as add_np_ticket_comment, but every row in one round trip
    instead of one per row — used by chat_turn's bot-phase-transcript ->
    ticket-thread copy at escalation time, where a query round trip to a
    cross-region Postgres instance dominates wall-clock time far more than
    the query itself does; N individual inserts there was the single
    biggest contributor to a slow-feeling escalation. Each row's
    attachment_data/attachment_name/attachment_mime are optional (None for a
    plain text turn) — carries over a file the customer attached during the
    bot phase, not just the text transcript."""
    if not rows:
        return
    now = _now()
    values_sql = ", ".join("(%s, %s, %s, %s, %s, %s, %s, %s)" for _ in rows)
    params = [
        p
        for r in rows
        for p in (
            np_ticket_id, r["author_role"], r["author_name"], r["text"], now,
            r.get("attachment_data"), r.get("attachment_name"), r.get("attachment_mime"),
        )
    ]
    with _conn() as conn:
        conn.execute(
            f"""INSERT INTO np_ticket_comments
               (np_ticket_id, author_role, author_name, body, created_at, attachment_data, attachment_name, attachment_mime)
               VALUES {values_sql}""",
            params,
        )


def upsert_np_periodic_report(period_type: str, period_key: str, payload: dict) -> None:
    with _conn() as conn:
        conn.execute(
            """INSERT INTO np_periodic_reports (period_type, period_key, payload_json, generated_at)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (period_type, period_key) DO UPDATE SET
                   payload_json = EXCLUDED.payload_json, generated_at = EXCLUDED.generated_at""",
            (period_type, period_key, json.dumps(payload), _now()),
        )


def get_np_periodic_report(period_type: str, period_key: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT payload_json FROM np_periodic_reports WHERE period_type = %s AND period_key = %s",
            (period_type, period_key),
        ).fetchone()
        return json.loads(row["payload_json"]) if row else None


def get_np_ticket_comment(comment_id: int) -> dict | None:
    """Includes attachment_data — only call this from the file-download
    endpoint, never anywhere the result gets JSON-serialized."""
    with _conn() as conn:
        row = conn.execute("SELECT * FROM np_ticket_comments WHERE id = %s", (comment_id,)).fetchone()
        return dict(row) if row else None


def list_np_ticket_comments_with_attachments(np_ticket_id: int) -> list[dict]:
    """Includes attachment_data — only for the PDF report generator, which
    reads the raw bytes to embed/merge attachments. Never JSON-serialize
    this; use list_np_ticket_comments for anything API-facing."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM np_ticket_comments WHERE np_ticket_id = %s ORDER BY created_at ASC", (np_ticket_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def list_np_ticket_comments(np_ticket_id: int) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            f"SELECT {_NP_COMMENT_JSON_COLUMNS} FROM np_ticket_comments WHERE np_ticket_id = %s ORDER BY created_at ASC",
            (np_ticket_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def mark_np_comments_read(np_ticket_id: int, viewer_role: str, viewer_key: str) -> None:
    with _conn() as conn:
        conn.execute(
            """INSERT INTO np_ticket_comment_reads (np_ticket_id, viewer_role, viewer_key, last_read_at)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (np_ticket_id, viewer_role, viewer_key) DO UPDATE SET last_read_at = EXCLUDED.last_read_at""",
            (np_ticket_id, viewer_role, viewer_key, _now()),
        )


def unread_np_comment_counts(ticket_ids: list[int], viewer_role: str, viewer_key: str) -> dict[int, int]:
    """Same shape as store.py's unread_comment_counts, scoped to np_tickets."""
    if not ticket_ids:
        return {}
    with _conn() as conn:
        placeholders = ",".join("%s" for _ in ticket_ids)
        last_reads = {
            row["np_ticket_id"]: row["last_read_at"]
            for row in conn.execute(
                f"""SELECT np_ticket_id, last_read_at FROM np_ticket_comment_reads
                    WHERE viewer_role = %s AND viewer_key = %s AND np_ticket_id IN ({placeholders})""",
                (viewer_role, viewer_key, *ticket_ids),
            ).fetchall()
        }
        rows = conn.execute(
            f"""SELECT np_ticket_id, created_at FROM np_ticket_comments
                WHERE np_ticket_id IN ({placeholders}) AND author_role != %s""",
            (*ticket_ids, viewer_role),
        ).fetchall()
        counts: dict[int, int] = {}
        for r in rows:
            last_read = last_reads.get(r["np_ticket_id"])
            if last_read is None or r["created_at"] > last_read:
                counts[r["np_ticket_id"]] = counts.get(r["np_ticket_id"], 0) + 1
        return counts


# ---- Nykaa Pulse's own feedback log -------------------------------------------

def save_np_feedback_item(
    source_type: str, text: str, sentiment_label: str, sentiment_score: float, category: str,
    urgency_score: float, is_actionable_ticket: bool | None, model_used: str, mode: str, latency_ms: int,
    source_ref: int | None = None, user_id: int | None = None, rating: int | None = None, theme: str | None = None,
    created_at: str | None = None,
) -> dict:
    with _conn() as conn:
        row = conn.execute(
            """INSERT INTO np_feedback_items (
                source_type, source_ref, user_id, rating, text, sentiment_label, sentiment_score, category, theme,
                urgency_score, is_actionable_ticket, model_used, mode, latency_ms, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *""",
            (
                source_type, source_ref, user_id, rating, text, sentiment_label, sentiment_score, category, theme,
                urgency_score, int(is_actionable_ticket) if is_actionable_ticket is not None else None,
                model_used, mode, latency_ms, created_at or _now(),
            ),
        ).fetchone()
        return dict(row)


# ---- app/website feedback (not about any product) -----------------------

def save_app_feedback(user_id: int | None, rating: int, categories: list[str], description: str | None) -> dict:
    with _conn() as conn:
        row = conn.execute(
            """INSERT INTO np_app_feedback (user_id, rating, category, categories_json, description, created_at)
               VALUES (%s, %s, %s, %s, %s, %s) RETURNING *""",
            (user_id, rating, ", ".join(categories), json.dumps(categories), description, _now()),
        ).fetchone()
        return dict(row)


def list_app_feedback(limit: int = 200) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM np_app_feedback ORDER BY created_at DESC LIMIT %s", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def compute_app_feedback_breakdown() -> dict:
    """Aggregate-only view of np_app_feedback for the PM's App Feedback tab
    — rating distribution + category counts, no raw feedback text. A
    submission can now name more than one category (categories_json), so
    counting happens in Python (one tally per category named, not per row)
    rather than a SQL GROUP BY — older rows with no categories_json fall
    back to their single `category` column."""
    with _conn() as conn:
        overall = conn.execute(
            "SELECT COUNT(*) AS n, AVG(rating) AS avg_rating FROM np_app_feedback"
        ).fetchone()
        by_rating = conn.execute(
            "SELECT rating, COUNT(*) AS n FROM np_app_feedback GROUP BY rating ORDER BY rating"
        ).fetchall()
        rows = conn.execute("SELECT category, categories_json FROM np_app_feedback").fetchall()

        category_counts: dict[str, int] = {}
        for r in rows:
            categories = json.loads(r["categories_json"]) if r["categories_json"] else [r["category"]]
            for c in categories:
                category_counts[c] = category_counts.get(c, 0) + 1
        category_breakdown = sorted(
            ({"category": c, "count": n} for c, n in category_counts.items()), key=lambda x: x["count"], reverse=True
        )

        return {
            "total": overall["n"],
            "avg_rating": round(float(overall["avg_rating"]), 2) if overall["avg_rating"] is not None else None,
            "rating_distribution": {r["rating"]: r["n"] for r in by_rating},
            "category_breakdown": category_breakdown,
        }


def compute_delivery_feedback_breakdown() -> dict:
    """Aggregate-only view of np_orders' delivery_rating/compliment for the
    PM's Delivery Feedback tab — rating distribution + how many left a
    compliment, no raw compliment text."""
    with _conn() as conn:
        overall = conn.execute(
            "SELECT COUNT(delivery_rating) AS n, AVG(delivery_rating) AS avg_rating, "
            "COUNT(*) FILTER (WHERE delivery_compliment IS NOT NULL AND delivery_compliment != '') AS with_compliment "
            "FROM np_orders"
        ).fetchone()
        by_rating = conn.execute(
            "SELECT delivery_rating AS rating, COUNT(*) AS n FROM np_orders "
            "WHERE delivery_rating IS NOT NULL GROUP BY delivery_rating ORDER BY delivery_rating"
        ).fetchall()
        return {
            "total": overall["n"],
            "avg_rating": round(float(overall["avg_rating"]), 2) if overall["avg_rating"] is not None else None,
            "with_compliment": overall["with_compliment"],
            "rating_distribution": {r["rating"]: r["n"] for r in by_rating},
        }


# ---- PM analytics (Phase 3) ---------------------------------------------------

def list_review_feedback_with_catalog() -> list[dict]:
    """Every np_feedback_items row for a Nykaa Pulse review, joined with which
    brand/catalog-category/product it's actually about. np_feedback_items
    itself has no notion of the catalog (it only knows feedback_ai's
    classification `category`) — this is the one place that bridges the
    two, so nykaa_insights.py can hand insights.py/narrative_ai.py rows
    shaped exactly like theirs, just relabeled by brand or catalog-category
    instead of feedback category."""
    with _conn() as conn:
        rows = conn.execute("""
            SELECT f.source_type, f.source_ref, f.user_id, f.text, f.sentiment_label, f.sentiment_score,
                   f.category, f.theme, f.urgency_score, f.is_actionable_ticket, f.rating, f.created_at,
                   b.name AS brand, c.name AS catalog_category, sc.name AS catalog_subcategory, p.name AS product_name
            FROM np_feedback_items f
            JOIN np_order_items oi ON oi.id = f.source_ref AND f.source_type = 'review'
            JOIN np_products p ON p.id = oi.product_id
            JOIN np_brands b ON b.id = p.brand_id
            JOIN np_categories c ON c.id = p.category_id
            JOIN np_subcategories sc ON sc.id = p.subcategory_id
        """).fetchall()
        return [dict(r) for r in rows]


def compute_order_funnel() -> dict:
    """Order → reviewed → photo-attached → published, the drop-off-step
    visibility the teardown flagged as missing from Nykaa's own PM view."""
    with _conn() as conn:
        row = conn.execute("""
            SELECT
                COUNT(*) AS total_items,
                COUNT(*) FILTER (WHERE rating IS NOT NULL OR review_title IS NOT NULL OR review_description IS NOT NULL) AS reviewed_items,
                COUNT(*) FILTER (WHERE review_photo_data IS NOT NULL) AS items_with_photo,
                COUNT(*) FILTER (WHERE review_status = 'published') AS published_items
            FROM np_order_items
        """).fetchone()
        return dict(row)


def compute_product_rollup(limit: int = 50) -> list[dict]:
    """Per-SKU rating/review-volume rollup — the "SKU rollups" the plan
    calls for, ranked by review volume so the most-discussed products (not
    just the worst-rated) surface first. avg_rating is None for a product
    with reviews but no star ratings."""
    with _conn() as conn:
        rows = conn.execute("""
            SELECT p.id AS product_id, p.name AS product_name, b.name AS brand, c.name AS category,
                   COUNT(oi.id) AS review_count,
                   AVG(oi.rating) FILTER (WHERE oi.rating IS NOT NULL) AS avg_rating,
                   COUNT(oi.rating) AS rated_count
            FROM np_order_items oi
            JOIN np_products p ON p.id = oi.product_id
            JOIN np_brands b ON b.id = p.brand_id
            JOIN np_categories c ON c.id = p.category_id
            WHERE oi.rating IS NOT NULL OR oi.review_title IS NOT NULL OR oi.review_description IS NOT NULL
            GROUP BY p.id, p.name, b.name, c.name
            ORDER BY review_count DESC
            LIMIT %s
        """, (limit,)).fetchall()
        return [
            {**dict(r), "avg_rating": round(float(r["avg_rating"]), 2) if r["avg_rating"] is not None else None}
            for r in rows
        ]


def compute_catalog_overview() -> dict:
    """Headline stats for the PM's Nykaa Pulse Overview sub-tab — order
    volume, review conversion, delivery satisfaction — none of which
    insights.py can compute since it only sees feedback_items, not
    orders/order_items."""
    with _conn() as conn:
        orders = conn.execute("SELECT COUNT(*) AS n, COALESCE(SUM(total_amount), 0) AS gmv FROM np_orders").fetchone()
        delivery = conn.execute(
            "SELECT AVG(delivery_rating) AS avg_delivery_rating, COUNT(delivery_rating) AS delivery_rated_count FROM np_orders"
        ).fetchone()
        items = conn.execute("""
            SELECT
                COUNT(*) AS total_items,
                AVG(rating) FILTER (WHERE rating IS NOT NULL) AS avg_rating,
                COUNT(rating) AS rated_count,
                COUNT(*) FILTER (WHERE linked_ticket_id IS NOT NULL) AS auto_or_manual_ticket_count
            FROM np_order_items
        """).fetchone()
        return {
            "total_orders": orders["n"],
            "total_gmv_inr": float(orders["gmv"]),
            "avg_delivery_rating": round(float(delivery["avg_delivery_rating"]), 2) if delivery["avg_delivery_rating"] is not None else None,
            "delivery_rated_count": delivery["delivery_rated_count"],
            "total_order_items": items["total_items"],
            "avg_rating": round(float(items["avg_rating"]), 2) if items["avg_rating"] is not None else None,
            "rated_count": items["rated_count"],
            "ticket_linked_count": items["auto_or_manual_ticket_count"],
        }
