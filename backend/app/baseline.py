"""A deliberately simple, keyword-only ticket classifier.

Serves two purposes in this project:
1. It's the offline fallback used when there's no API key / FORCE_MOCK_MODE=true,
   so the whole app is demoable without ever touching the network.
2. It's the "naive baseline" shown side-by-side with Claude's classification,
   so the difference between keyword matching and real language understanding
   is something you can point at on screen instead of just asserting.

Nothing here calls an LLM. It is intentionally rigid: no notion of sarcasm,
negation, multi-issue tickets, or context — which is exactly the point.
"""
import re

from .models import Category, Priority, Team, Tone

CATEGORY_TEAM_MAP: dict[Category, Team] = {
    Category.ORDER_ISSUE: Team.ORDER_DELIVERY_TEAM,
    Category.PAYMENTS_REFUNDS: Team.PAYMENTS_BILLING_TEAM,
    Category.RETURNS_REPLACEMENTS: Team.RETURNS_REFUNDS_TEAM,
    Category.PRODUCT_QUALITY_SAFETY: Team.PRODUCT_QUALITY_TEAM,
    Category.APP_WEBSITE_ISSUE: Team.TECHNICAL_SUPPORT_TEAM,
    Category.ACCOUNT_ACCESS: Team.ACCOUNT_LOYALTY_TEAM,
    Category.SELLER_VENDOR_ISSUE: Team.TRIAGE,
    Category.GENERAL_INQUIRY: Team.TRIAGE,
}

_KEYWORDS: dict[Category, list[str]] = {
    Category.ORDER_ISSUE: ["hasn't arrived", "has not arrived", "never received", "not delivered",
                            "delivery delay", "delayed", "wrong item", "wrong product shipped",
                            "package lost", "lost my package", "cancel my order", "non-delivery"],
    Category.PAYMENTS_REFUNDS: ["charged twice", "charged", "double charged", "refund", "invoice",
                                 "billing", "payment failed", "coupon", "discount code", "wallet",
                                 "cashback", "price"],
    Category.RETURNS_REPLACEMENTS: ["return", "replace", "replacement", "exchange", "wrong shade",
                                     "wrong size", "want to return", "return window", "swap it"],
    Category.PRODUCT_QUALITY_SAFETY: ["damaged", "expired", "leaking", "leaked", "broken seal",
                                       "tampered", "counterfeit", "fake product", "allergic",
                                       "allergy", "reaction", "smells off", "spoiled"],
    Category.APP_WEBSITE_ISSUE: ["app crashed", "app keeps crashing", "website down", "site is down",
                                  "checkout failed", "won't load", "not loading", "glitch",
                                  "freezes", "freeze", "500 error", "error message"],
    Category.ACCOUNT_ACCESS: ["can't log in", "cannot log in", "locked out", "forgot password",
                               "reset my password", "login", "log in", "sign in", "account access", "otp", "mfa"],
    Category.SELLER_VENDOR_ISSUE: ["seller", "vendor", "third-party seller", "marketplace seller",
                                    "seller not responding", "seller hasn't responded"],
}

_URGENT_WORDS = ["urgent", "asap", "immediately", "emergency", "right now", "critical"]
_ANGRY_WORDS = ["angry", "furious", "ridiculous", "unacceptable", "worst", "terrible",
                "scam", "disgusted", "outraged", "fed up", "sick of"]
_FRUSTRATED_WORDS = ["frustrated", "annoyed", "disappointed", "again", "still not", "third time"]
_WORRIED_WORDS = ["worried", "concerned", "concerning", "afraid", "scared", "nervous", "anxious",
                  "is this normal", "hope this isn't", "hope my", "is my account safe"]


def _score_categories(text: str) -> dict[Category, int]:
    scores = {cat: 0 for cat in Category}
    for cat, words in _KEYWORDS.items():
        for w in words:
            if w in text:
                scores[cat] += 1
    return scores


def _guess_tone(text: str, raw: str) -> Tone:
    exclaim = raw.count("!")
    caps_words = [w for w in re.findall(r"[A-Za-z]{3,}", raw) if w.isupper()]
    if any(w in text for w in _ANGRY_WORDS) or exclaim >= 3 or len(caps_words) >= 2:
        return Tone.ANGRY
    if any(w in text for w in _FRUSTRATED_WORDS) or exclaim >= 1:
        return Tone.FRUSTRATED
    if any(w in text for w in _URGENT_WORDS):
        return Tone.URGENT
    if any(w in text for w in _WORRIED_WORDS):
        return Tone.WORRIED
    if any(w in text for w in ["thanks", "thank you", "great", "love", "awesome"]):
        return Tone.POSITIVE
    if "?" in raw and len(raw.split()) < 8:
        return Tone.CONFUSED
    return Tone.NEUTRAL


def _guess_priority(text: str, tone: Tone, category: Category) -> Priority:
    if category == Category.PRODUCT_QUALITY_SAFETY:
        return Priority.HIGH
    if any(w in text for w in _URGENT_WORDS) or tone == Tone.ANGRY:
        return Priority.HIGH
    if category in (Category.ORDER_ISSUE, Category.PAYMENTS_REFUNDS, Category.ACCOUNT_ACCESS) or tone == Tone.FRUSTRATED:
        return Priority.MEDIUM
    return Priority.LOW


class BaselineOutcome:
    def __init__(self, category: Category, priority: Priority, team: Team, tone: Tone, reasoning: str):
        self.category = category
        self.priority = priority
        self.team = team
        self.tone = tone
        self.reasoning = reasoning


def classify(message: str) -> BaselineOutcome:
    text = message.lower()
    scores = _score_categories(text)
    best_cat = max(scores, key=lambda c: scores[c])
    matched = scores[best_cat]

    if matched == 0:
        best_cat = Category.GENERAL_INQUIRY
        reasoning = "No keyword matches found; defaulted to General Inquiry."
    else:
        hit_words = [w for w in _KEYWORDS[best_cat] if w in text]
        reasoning = f"Matched keyword(s): {', '.join(hit_words[:3])}."

    tone = _guess_tone(text, message)
    priority = _guess_priority(text, tone, best_cat)
    team = CATEGORY_TEAM_MAP[best_cat]

    return BaselineOutcome(best_cat, priority, team, tone, reasoning)
