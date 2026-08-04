"""Synthetic 2-year demo dataset: CSV generation + import, for both products.

Two separate steps, mirroring a real ETL flow rather than one opaque
function: `generate_*_csv(s)` writes plain CSV files under backend/data/seed/
so they can be opened and inspected before anything touches the database;
`import_*_csv` reads those files back in and inserts the rows.

Deliberately LLM-free and deterministic: every row's sentiment/category/team
is derived directly from which template generated it, not a live AI call —
this can regenerate and reimport instantly, for free, as many times as
needed. The real live classifier/feedback_ai pipeline is untouched and still
handles every genuine user-submitted ticket/review/survey; this only
back-fills historical volume so period-over-period charts and reports have
more than a handful of live-demo rows to work with.

Rows are attributed to a small, fixed pool of demo "user" accounts (see
DEMO_USERS) with a known password, so this data is also visible by actually
logging in as one of them — not just from the PM/admin side.
"""
import csv
import random
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import auth, baseline, nykaa_seed, nykaa_store as npstore, store
from .models import Category, FeedbackCategory, Priority, SentimentLabel, Team, Tone

SEED_DIR = Path(__file__).parent.parent / "data" / "seed"

DEMO_USERS = [
    {"name": "Aisha Khan", "email": "aisha.demo@example.com"},
    {"name": "Rohan Mehta", "email": "rohan.demo@example.com"},
    {"name": "Priya Sharma", "email": "priya.demo@example.com"},
    {"name": "Karan Verma", "email": "karan.demo@example.com"},
    {"name": "Sneha Iyer", "email": "sneha.demo@example.com"},
]
DEMO_PASSWORD = "Demo@1234"

TICKET_TRIDENT_ROWS = 220
# The catalog has ~34 distinct brands (some categories introduce brands not
# used anywhere else) — 8/brand keeps the Nykaa Pulse total in the same
# "small demo set" ballpark (~270 rows) as the Ticket Trident CSV above,
# while still covering every brand/category/subcategory at least once.
ROWS_PER_BRAND = 8

TICKET_TEMPLATES = {
    Category.ORDER_ISSUE: [
        "My order #{n} still hasn't arrived and it's been over a week since the estimated delivery date.",
        "The package I received had the wrong product inside — I ordered something else entirely.",
        "Tracking shows my order left the warehouse three days ago and hasn't moved since.",
        "I'd like to cancel order #{n}, it hasn't shipped yet and I no longer need it.",
        "My package arrived damaged and a couple of items were missing from the box.",
    ],
    Category.PAYMENTS_REFUNDS: [
        "I was charged twice for the same order and need one of the charges reversed.",
        "My refund for a returned item still hasn't shown up in my account after two weeks.",
        "The coupon code I applied at checkout didn't actually reduce the total.",
        "My wallet balance doesn't match what I'd expect after a recent refund.",
        "I think I was overcharged compared to the price shown on the product page.",
    ],
    Category.RETURNS_REPLACEMENTS: [
        "I'd like to exchange this for a different shade — the one I got doesn't match my skin tone.",
        "The return portal says my order isn't eligible even though it's within the return window.",
        "Can you help me start a replacement request for a product that arrived in the wrong size?",
        "I want to return this item, it just isn't what I expected from the photos.",
        "I'd like to cancel this return request, I've changed my mind and want to keep the item.",
    ],
    Category.PRODUCT_QUALITY_SAFETY: [
        "The product arrived with a broken safety seal and I'm not sure it's safe to use.",
        "This item leaked all over the box during shipping and the packaging was damaged.",
        "I had a mild allergic reaction after using this and wanted to flag it.",
        "The batch code on this product shows it expired two months ago.",
        "I'm fairly sure this is a counterfeit, the box print looks different from what I got last time.",
    ],
    Category.APP_WEBSITE_ISSUE: [
        "The checkout page keeps freezing right before I can complete payment.",
        "The app crashes every time I try to open my wishlist.",
        "Product pages aren't loading properly on the site today.",
        "The search bar returns no results even for products I know you sell.",
        "I keep getting logged out mid-checkout, which is really disruptive.",
    ],
    Category.ACCOUNT_ACCESS: [
        "I can't log into my account even though I'm sure my password is correct.",
        "I'm locked out of my account and need help resetting access.",
        "My OTP codes have stopped arriving by SMS for the past couple of days.",
        "I forgot my password and the reset email never arrived.",
    ],
    Category.SELLER_VENDOR_ISSUE: [
        "The third-party seller for this item hasn't responded to my message in several days.",
        "I'm not sure this seller is authorized for this brand, the listing photos look off.",
    ],
    Category.GENERAL_INQUIRY: [
        "Just wanted to say the new packaging redesign looks great, nice work.",
        "What are your customer service hours on weekends?",
        "I've noticed response times have gotten a bit slower lately, just flagging it.",
        "Do you have any upcoming sales planned for this category?",
    ],
}

# Mirrors classifier.py's priority-guidance rules (severity, not tone-driven).
_PRIORITY_BY_CATEGORY = {
    Category.PRODUCT_QUALITY_SAFETY: Priority.HIGH,
    Category.ORDER_ISSUE: Priority.MEDIUM,
    Category.PAYMENTS_REFUNDS: Priority.MEDIUM,
    Category.ACCOUNT_ACCESS: Priority.MEDIUM,
}

SURVEY_TEMPLATES = {
    5: ["Really happy with how this turned out, will shop again.", "Excellent experience end to end.", "Exactly what I was hoping for."],
    4: ["Pretty good overall, minor things could be better.", "Happy with this, would recommend."],
    3: ["It was okay, nothing special either way.", "Average experience, gets the job done."],
    2: ["Not great, a few things went wrong.", "Disappointed with parts of this."],
    1: ["Would not recommend, this didn't work out well.", "Pretty frustrating experience overall."],
}

# Skewed toward positive, same shape real feedback usually takes.
_RATING_POOL = [1, 2, 3, 4, 4, 5, 5, 5]


def _sentiment_from_rating(rating: int) -> tuple[str, float]:
    if rating >= 4:
        return SentimentLabel.POSITIVE.value, 0.6
    if rating == 3:
        return SentimentLabel.NEUTRAL.value, 0.0
    return SentimentLabel.NEGATIVE.value, -0.6


def _spread_dates(n: int, rng: random.Random) -> list[str]:
    """n ISO dates spread evenly (with jitter) across the last 2 years,
    oldest first — gives period-over-period charts real historical depth
    instead of every seeded row landing in the current period."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=365 * 2)
    span_seconds = (end - start).total_seconds()
    if n <= 1:
        return [end.isoformat()]
    dates = []
    for i in range(n):
        base = start + timedelta(seconds=span_seconds * i / (n - 1))
        jitter = timedelta(hours=rng.uniform(-36, 36))
        dates.append((base + jitter).isoformat())
    return sorted(dates)


def _ensure_demo_users() -> list[dict]:
    """Idempotent — reuses existing accounts by email rather than erroring
    or duplicating them on a second run."""
    store.init_db()
    users = []
    for u in DEMO_USERS:
        existing = store.get_user_by_email(u["email"])
        users.append(existing if existing else store.create_user(u["name"], u["email"], auth.hash_password(DEMO_PASSWORD)))
    return users


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


# ---- generation ------------------------------------------------------------

def generate_ticket_trident_csv(seed: int = 42) -> Path:
    """One CSV covering every Category (and, by extension, every Team via
    baseline.CATEGORY_TEAM_MAP) for Ticket Trident."""
    rng = random.Random(seed)
    users = _ensure_demo_users()
    categories = list(TICKET_TEMPLATES.keys())
    dates = _spread_dates(TICKET_TRIDENT_ROWS, rng)

    SEED_DIR.mkdir(parents=True, exist_ok=True)
    path = SEED_DIR / "ticket_trident_feedback.csv"
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["user_email", "category", "feedback", "rating", "survey_response", "date"])
        for i in range(TICKET_TRIDENT_ROWS):
            category = categories[i % len(categories)]
            user = users[i % len(users)]
            rating = rng.choice(_RATING_POOL)
            feedback = rng.choice(TICKET_TEMPLATES[category]).format(n=1000 + i)
            survey_response = rng.choice(SURVEY_TEMPLATES[rating])
            writer.writerow([user["email"], category.value, feedback, rating, survey_response, dates[i]])
    return path


def generate_nykaa_pulse_csvs(seed: int = 42, rows_per_brand: int = ROWS_PER_BRAND) -> list[Path]:
    """One CSV per brand — covers every brand/category/subcategory
    combination the seeded catalog has, since every row is generated
    against a real product (and that product's own theme vocabulary)."""
    rng = random.Random(seed)
    store.init_db()
    npstore.init_nykaa_db()
    nykaa_seed.seed_catalog()
    users = _ensure_demo_users()

    by_brand: dict[str, list[dict]] = {}
    for p in npstore.list_products():
        by_brand.setdefault(p["brand_name"], []).append(p)

    SEED_DIR.mkdir(parents=True, exist_ok=True)
    paths = []
    for brand, products in sorted(by_brand.items()):
        dates = _spread_dates(rows_per_brand, rng)
        path = SEED_DIR / f"nykaa_pulse_{_slugify(brand)}.csv"
        with path.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["user_email", "brand", "category", "subcategory", "product_name", "feedback", "rating", "survey_response", "date"])
            for i in range(rows_per_brand):
                product = products[i % len(products)]
                user = users[i % len(users)]
                rating = rng.choice(_RATING_POOL)
                theme_pool = product["positive_themes"] if rating >= 4 else product["negative_themes"] if rating <= 2 else (product["positive_themes"] + product["negative_themes"])
                theme = rng.choice(theme_pool) if theme_pool else "General"
                feedback = f"{theme} — {'really pleased' if rating >= 4 else 'disappointed' if rating <= 2 else 'mixed feelings'} with the {product['name']}."
                survey_response = rng.choice(SURVEY_TEMPLATES[rating])
                writer.writerow([
                    user["email"], brand, product["category_name"], product["subcategory_name"], product["name"],
                    feedback, rating, survey_response, dates[i],
                ])
        paths.append(path)
    return paths


# ---- import ----------------------------------------------------------------

def _insert_seed_ticket(*, user_id, message, category, priority, team, tone, confidence, reasoning, created_at) -> None:
    """Raw insert rather than store.save_ticket — that function always
    attributes rows to the fixed admin-sandbox user, but seeded rows need to
    be attributed to real demo accounts so they show up on those accounts'
    own "My Tickets" page."""
    with store._conn() as conn:
        conn.execute(
            """INSERT INTO tickets (
                user_id, message, status, category, priority, team, tone, confidence, is_ambiguous,
                escalated, reasoning, model_used, mode, latency_ms, created_at
            ) VALUES (%s, %s, 'Routed', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (user_id, message, category, priority, team, tone, confidence, 0, 0, reasoning, "seed-script", "seed", 0, created_at),
        )


def import_ticket_trident_csv(path: Path | None = None) -> int:
    path = path or (SEED_DIR / "ticket_trident_feedback.csv")
    store.init_db()
    users_by_email = {u["email"]: u for u in _ensure_demo_users()}

    count = 0
    with path.open(newline="") as f:
        for row in csv.DictReader(f):
            user = users_by_email.get(row["user_email"])
            user_id = user["id"] if user else None
            category = Category(row["category"])
            team = baseline.CATEGORY_TEAM_MAP[category]
            priority = _PRIORITY_BY_CATEGORY.get(category, Priority.LOW)
            rating = int(row["rating"])
            sentiment_label, sentiment_score = _sentiment_from_rating(rating)
            created_at = row["date"]

            _insert_seed_ticket(
                user_id=user_id, message=row["feedback"], category=category.value, priority=priority.value,
                team=team.value, tone=Tone.NEUTRAL.value, confidence=0.75, reasoning="Seeded demo data.",
                created_at=created_at,
            )
            store.save_feedback_item(
                source_type="survey", text=row["survey_response"], sentiment_label=sentiment_label,
                sentiment_score=sentiment_score, category=category.value,
                urgency_score=0.3 if rating >= 3 else 0.6, is_actionable_ticket=rating <= 2,
                model_used="seed-script", mode="seed", latency_ms=0, user_id=user_id, rating=rating,
                created_at=created_at,
            )
            count += 1
    return count


def _insert_seed_order(user_id: int, product: dict, rating: int, review_text: str, delivery_comment: str, created_at: str) -> int:
    """Raw insert of a one-item, already-delivered order + its review — the
    real join PM analytics needs (list_review_feedback_with_catalog) requires
    np_feedback_items.source_ref to point at a genuine np_order_items row, not
    just a bare feedback row. Returns the new np_order_items.id."""
    price = float(product["price_inr"])
    with npstore._conn() as conn:
        order = conn.execute(
            """INSERT INTO np_orders (user_id, status, placed_at, delivered_at, total_amount, delivery_rating, delivery_compliment)
               VALUES (%s, 'Delivered', %s, %s, %s, %s, %s) RETURNING id""",
            (user_id, created_at, created_at, price, rating, delivery_comment),
        ).fetchone()
        item = conn.execute(
            """INSERT INTO np_order_items (
                order_id, product_id, quantity, unit_price_at_purchase, rating, review_title, review_description,
                review_status, created_at
            ) VALUES (%s, %s, 1, %s, %s, %s, %s, 'published', %s) RETURNING id""",
            (order["id"], product["id"], price, rating, review_text[:60], review_text, created_at),
        ).fetchone()
        return item["id"]


def import_nykaa_pulse_csvs(paths: list[Path] | None = None) -> int:
    if paths is None:
        paths = sorted(SEED_DIR.glob("nykaa_pulse_*.csv"))
    store.init_db()
    npstore.init_nykaa_db()
    users_by_email = {u["email"]: u for u in _ensure_demo_users()}
    products_by_name = {p["name"]: p for p in npstore.list_products()}
    feedback_categories = list(FeedbackCategory)

    count = 0
    for path in paths:
        with path.open(newline="") as f:
            for row in csv.DictReader(f):
                user = users_by_email.get(row["user_email"])
                product = products_by_name.get(row["product_name"])
                if user is None or product is None:
                    continue
                rating = int(row["rating"])
                created_at = row["date"]
                sentiment_label, sentiment_score = _sentiment_from_rating(rating)
                theme = row["feedback"].split(" — ", 1)[0]
                # Cycled by a counter running across every brand's CSV (not
                # reset per file, and not tied to rating/product) so every
                # FeedbackCategory bucket gets covered across the full
                # import, matching "cover all categories" rather than
                # skewing toward whichever categories happen to correlate
                # with sentiment, or silently never reaching the last couple
                # of categories because each file's own index never got that far.
                category = feedback_categories[count % len(feedback_categories)]

                item_id = _insert_seed_order(user["id"], product, rating, row["feedback"], row["survey_response"], created_at)
                npstore.save_np_feedback_item(
                    source_type="review", source_ref=item_id, user_id=user["id"], rating=rating,
                    text=row["feedback"], sentiment_label=sentiment_label, sentiment_score=sentiment_score,
                    category=category.value, theme=theme, urgency_score=0.3 if rating >= 3 else 0.6,
                    is_actionable_ticket=rating <= 2, model_used="seed-script", mode="seed", latency_ms=0,
                    created_at=created_at,
                )
                count += 1
    return count


def generate_all(seed: int = 42) -> list[Path]:
    return [generate_ticket_trident_csv(seed), *generate_nykaa_pulse_csvs(seed)]


def import_all() -> dict[str, int]:
    return {
        "ticket_trident": import_ticket_trident_csv(),
        "nykaa_pulse": import_nykaa_pulse_csvs(),
    }
