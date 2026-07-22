"""Hand-labeled feedback samples for evaluating feedback_ai.analyze_feedback.

Mirrors sample_tickets.py's role for the ticket classifier — a fixed,
realistic set with ground truth attached, so accuracy is a measured number
rather than an impression. Deliberately spans every dimension the pipeline
judges, plus the edge cases most likely to trip it up:
- all 4 sentiment labels (positive, neutral, negative, mixed)
- both actionable and non-actionable feedback, including negative-but-not-
  actionable (pure venting) and positive-but-actionable (a feature request)
- the vague/near-empty edge case
- a non-English message (reasoning/theme must still be in English)
- sarcasm, where the literal words skew one way but the intent is another

`theme_keywords` isn't a single expected string — themes are free text (see
feedback_ai.py's rationale for why), so grading is "does the generated theme
contain at least one of these substrings," not exact match. That's a
deliberately loose bar: it tests whether the theme is *about the right
thing*, not whether it's phrased identically to some fixed taxonomy entry.
"""

SAMPLE_FEEDBACK = [
    {
        "text": "I was charged twice for my subscription this month and support hasn't replied in a week.",
        "source_type": "ticket",
        "expected_sentiment": "negative",
        "expected_actionable": True,
        "theme_keywords": ["billing", "charge", "duplicate", "subscription"],
        "tag": "billing_actionable_negative",
    },
    {
        "text": "Just wanted to say the new dashboard redesign looks great, really clean.",
        "source_type": "review",
        "expected_sentiment": "positive",
        "expected_actionable": False,
        "theme_keywords": ["dashboard", "redesign", "praise", "ui"],
        "tag": "praise_not_actionable",
    },
    {
        "text": "Love the app overall but the export button has been broken for two weeks now.",
        "source_type": "review",
        "expected_sentiment": "mixed",
        "expected_actionable": True,
        "theme_keywords": ["export"],
        "tag": "mixed_sentiment_actionable",
    },
    {
        "text": "meh",
        "source_type": "survey",
        "expected_sentiment": "neutral",
        "expected_actionable": False,
        "theme_keywords": ["insufficient", "detail", "vague", "unclear"],
        "tag": "vague_edge_case",
    },
    {
        "text": "I've been a loyal customer for years and I'm just disappointed things have changed so much.",
        "source_type": "review",
        "expected_sentiment": "negative",
        "expected_actionable": False,
        "theme_keywords": ["disappoint", "loyal", "chang", "general"],
        "tag": "negative_not_actionable_venting",
    },
    {
        "text": "It would be amazing if you could add a dark mode toggle to the mobile app too.",
        "source_type": "review",
        "expected_sentiment": "positive",
        "expected_actionable": True,
        "theme_keywords": ["dark mode", "feature", "mobile"],
        "tag": "feature_request_actionable",
    },
    {
        "text": "The app crashed while I was uploading photos and now I can't find them anywhere. Did I lose them?",
        "source_type": "ticket",
        "expected_sentiment": "negative",
        "expected_actionable": True,
        "theme_keywords": ["crash", "photo", "data loss", "upload"],
        "tag": "bug_data_loss_urgent",
    },
    {
        "text": "Oh sure, ANOTHER update that breaks the login page. Really appreciate that.",
        "source_type": "review",
        "expected_sentiment": "negative",
        "expected_actionable": True,
        "theme_keywords": ["login", "bug", "update"],
        "tag": "sarcasm_negative_actionable",
    },
    {
        "text": "Quick question - does the annual plan renew automatically, or do I need to manually renew each year?",
        "source_type": "ticket",
        "expected_sentiment": "neutral",
        "expected_actionable": True,
        "theme_keywords": ["renew", "plan", "billing", "annual"],
        "tag": "calm_billing_question",
    },
    {
        "text": "El soporte al cliente fue excelente, resolvieron mi problema en minutos.",
        "source_type": "review",
        "expected_sentiment": "positive",
        "expected_actionable": False,
        "theme_keywords": ["support", "soporte", "service", "praise"],
        "tag": "non_english_positive",
    },
    {
        "text": "This is the third time this month the app has logged me out mid-session. Extremely frustrating.",
        "source_type": "review",
        "expected_sentiment": "negative",
        "expected_actionable": True,
        "theme_keywords": ["logout", "session", "log out", "login"],
        "tag": "recurring_bug_frustrated",
    },
    {
        "text": "",
        "source_type": "survey",
        "expected_sentiment": "neutral",
        "expected_actionable": False,
        "theme_keywords": ["insufficient", "detail", "empty"],
        "tag": "empty_input_edge_case",
    },
    {
        "text": "Thanks for the quick fix on the payment bug, everything works perfectly now!",
        "source_type": "review",
        "expected_sentiment": "positive",
        "expected_actionable": False,
        "theme_keywords": ["payment", "fix", "thanks", "praise"],
        "tag": "positive_confirms_fix",
    },
    {
        "text": "Our production integration has been returning 500 errors for the last 20 minutes, this is affecting checkout.",
        "source_type": "ticket",
        "expected_sentiment": "negative",
        "expected_actionable": True,
        "theme_keywords": ["500", "error", "outage", "integration", "checkout"],
        "tag": "outage_high_urgency",
    },
    {
        "text": "The onboarding flow is fine, nothing special but it gets the job done.",
        "source_type": "review",
        "expected_sentiment": "neutral",
        "expected_actionable": False,
        "theme_keywords": ["onboarding", "flow"],
        "tag": "neutral_calm_feedback",
    },
    {
        "text": "Rating: 2/5 stars. The mobile app is so slow it's basically unusable during peak hours.",
        "source_type": "survey",
        "expected_sentiment": "negative",
        "expected_actionable": True,
        "theme_keywords": ["slow", "performance", "mobile", "unusable"],
        "tag": "survey_performance_complaint",
    },
]
