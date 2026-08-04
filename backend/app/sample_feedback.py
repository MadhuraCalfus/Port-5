"""Hand-labeled feedback samples for evaluating feedback_ai.analyze_feedback.

Mirrors sample_tickets.py's role for the ticket classifier — a fixed,
realistic set with ground truth attached, so accuracy is a measured number
rather than an impression. Deliberately spans every dimension the pipeline
judges, plus the edge cases most likely to trip it up:
- all 3 sentiment labels (positive, neutral, negative)
- both actionable and non-actionable feedback, including negative-but-not-
  actionable (pure venting) and positive-but-actionable (a feature request)
- the vague/near-empty edge case
- a non-English message (reasoning/category must still be in English)
- sarcasm, where the literal words skew one way but the intent is another
- all 10 fixed categories at least once, plus the "General Praise / Other" fallback
- a Packaging & Damage vs. Delivery & Logistics pair, since that's the one
  category split that's genuinely ambiguous (product condition vs. shipment timing)

`expected_category` is one of the fixed FeedbackCategory values and graded
by exact match — categories are a closed taxonomy (see feedback_ai.py), so
unlike theme there's no substring/keyword fuzziness left to allow for.
`expected_theme` is a looser ground-truth hint, not graded for exact match
(theme is intentionally open vocabulary) — see feedback_eval.py. A couple of
samples sit close to the boundary between two valid categories (e.g. a
late-shipment complaint) — the label picked here is the one
feedback_ai.SYSTEM_PROMPT's own tie-break rule ("most dominant/specific")
points to.
"""

SAMPLE_FEEDBACK = [
    {
        "text": "I was charged twice for my order this month and support hasn't replied in a week.",
        "source_type": "ticket",
        "expected_sentiment": "negative",
        "expected_actionable": True,
        "expected_category": "Pricing & Offers",
        "expected_theme": "Hidden Charges",
        "tag": "pricing_actionable_negative",
    },
    {
        "text": "Just wanted to say the new checkout redesign looks great, so much easier to use now.",
        "source_type": "review",
        "expected_sentiment": "positive",
        "expected_actionable": False,
        "expected_category": "Review & App Flow Friction",
        "expected_theme": "Checkout Experience",
        "tag": "praise_not_actionable",
    },
    {
        "text": "Love the brand overall but the same lipstick shade has looked patchy the last two times I've bought it.",
        "source_type": "review",
        "expected_sentiment": "negative",
        "expected_actionable": True,
        "expected_category": "Product Quality & Fit",
        "expected_theme": "Inconsistent Quality",
        "tag": "praise_plus_unresolved_quality_reads_negative",
    },
    {
        "text": "meh",
        "source_type": "survey",
        "expected_sentiment": "neutral",
        "expected_actionable": False,
        "expected_category": "General Praise / Other",
        "expected_theme": "Insufficient Detail",
        "tag": "vague_edge_case",
    },
    {
        "text": "I've shopped here for years and I'm just disappointed things aren't quite what they used to be.",
        "source_type": "review",
        "expected_sentiment": "negative",
        "expected_actionable": False,
        "expected_category": "General Praise / Other",
        "expected_theme": "Mixed Feedback",
        "tag": "negative_not_actionable_venting",
    },
    {
        "text": "It would be amazing if you had a shade-matching quiz that actually accounts for undertone, not just depth.",
        "source_type": "review",
        "expected_sentiment": "positive",
        "expected_actionable": True,
        "expected_category": "Personalization Mismatch",
        "expected_theme": "Shade Finder Inaccurate",
        "tag": "feature_request_actionable",
    },
    {
        "text": "The sunscreen bottle arrived completely empty even though the box looked sealed. Where did the product go?",
        "source_type": "ticket",
        "expected_sentiment": "negative",
        "expected_actionable": True,
        "expected_category": "Packaging & Damage",
        "expected_theme": "Missing Item in Box",
        "tag": "packaging_missing_urgent",
    },
    {
        "text": "Oh sure, ANOTHER order that shows 'delivered' when nothing is actually on my doorstep.",
        "source_type": "review",
        "expected_sentiment": "negative",
        "expected_actionable": True,
        "expected_category": "Delivery & Logistics",
        "expected_theme": "Non-Delivery",
        "tag": "sarcasm_negative_actionable",
    },
    {
        "text": "The packaging on this palette looks different from my last order — no hologram sticker on the box this time. Is this still authentic?",
        "source_type": "ticket",
        "expected_sentiment": "neutral",
        "expected_actionable": True,
        "expected_category": "Authenticity & Trust",
        "expected_theme": "Missing Seal",
        "tag": "authenticity_question_neutral",
    },
    {
        "text": "El servicio al cliente fue excelente, resolvieron mi problema en minutos.",
        "source_type": "review",
        "expected_sentiment": "positive",
        "expected_actionable": False,
        "expected_category": "Customer Support",
        "expected_theme": "Helpful Support",
        "tag": "non_english_positive",
    },
    {
        "text": "This is the third time this month my review has gotten stuck in moderation for over a week before showing up.",
        "source_type": "review",
        "expected_sentiment": "negative",
        "expected_actionable": True,
        "expected_category": "Rewards & Loyalty",
        "expected_theme": "Moderation Delay",
        "tag": "recurring_moderation_frustrated",
    },
    {
        "text": "",
        "source_type": "survey",
        "expected_sentiment": "neutral",
        "expected_actionable": False,
        "expected_category": "General Praise / Other",
        "expected_theme": "Insufficient Detail",
        "tag": "empty_input_edge_case",
    },
    {
        "text": "Thanks for crediting my reward points after I flagged it, everything's sorted now!",
        "source_type": "review",
        "expected_sentiment": "positive",
        "expected_actionable": False,
        "expected_category": "Rewards & Loyalty",
        "expected_theme": "Points Not Credited",
        "tag": "positive_confirms_fix",
    },
    {
        "text": "Our bulk order for the store event arrived with three items visibly cracked and leaking inside sealed boxes, this is affecting our launch tomorrow.",
        "source_type": "ticket",
        "expected_sentiment": "negative",
        "expected_actionable": True,
        "expected_category": "Packaging & Damage",
        "expected_theme": "Cracked Container",
        "tag": "damage_high_urgency",
    },
    {
        "text": "The order-tracking page is fine, nothing special but it gets the job done.",
        "source_type": "review",
        "expected_sentiment": "neutral",
        "expected_actionable": False,
        "expected_category": "Review & App Flow Friction",
        "expected_theme": "Ease of Use",
        "tag": "neutral_calm_feedback",
    },
    {
        "text": "Rating: 2/5 stars. My order shipped five days after I placed it and is still not marked as dispatched.",
        "source_type": "survey",
        "expected_sentiment": "negative",
        "expected_actionable": True,
        "expected_category": "Delivery & Logistics",
        "expected_theme": "Late Delivery",
        "tag": "survey_delivery_complaint",
    },
    {
        "text": "I never got a confirmation that my order actually went through, had to check my orders page manually to be sure.",
        "source_type": "ticket",
        "expected_sentiment": "negative",
        "expected_actionable": True,
        "expected_category": "Review & App Flow Friction",
        "expected_theme": "Checkout Bug",
        "tag": "missing_confirmation_actionable",
    },
    {
        "text": "The weekly best-sellers email is genuinely useful but I can't tell why some out-of-stock items are still recommended to me.",
        "source_type": "review",
        "expected_sentiment": "neutral",
        "expected_actionable": True,
        "expected_category": "Personalization Mismatch",
        "expected_theme": "Irrelevant Recommendation",
        "tag": "personalization_clarity_neutral",
    },
    {
        "text": "Honestly this brand has made my whole skincare routine so much easier, I love how consistent the quality has been.",
        "source_type": "review",
        "expected_sentiment": "positive",
        "expected_actionable": False,
        "expected_category": "General Praise / Other",
        "expected_theme": "Reliable Brand",
        "tag": "general_praise_pure",
    },
    {
        "text": "The product page took forever to load every single time I opened it, but at least checkout didn't crash on me.",
        "source_type": "ticket",
        "expected_sentiment": "negative",
        "expected_actionable": True,
        "expected_category": "Review & App Flow Friction",
        "expected_theme": "Slow Loading",
        "tag": "friction_not_crash_disambiguation",
    },
]
