"""30 sample tickets for the mission's demo requirement.

Deliberately spans every dimension the classifier assigns, so a run of
`python -m app.cli demo` (or the Demo tab) gives a mentor a real look at the
AI routing across the full matrix — confirmed against a live run of the
classifier, not just designed on paper:
- all 7 tones (neutral, frustrated, angry, urgent, confused, worried, positive)
- all 3 priorities (High, Medium, Low), including cases that only reach High
  via the frustrated/angry/urgent escalation rule so that behavior is visible
- all 7 teams (Triage, Order & Delivery Team, Returns & Refunds Team,
  Payments & Billing Team, Product Quality Team, Technical Support Team,
  Account & Loyalty Team)

Also keeps the 3 required edge cases (angry tone, very short message,
ambiguous ticket) plus a few extra curveballs (sarcasm, multi-issue,
non-English-keyword phrasing) that the keyword baseline is expected to get
wrong, to make the AI-vs-baseline comparison land during the demo.

Tags describe what's notable about the ticket, not a guaranteed outcome —
tone/priority/confidence are the live model's judgment call and can shift
slightly between runs or providers.
"""

SAMPLE_TICKETS = [
    # Order & Delivery Team (category: Order Issue)
    {"text": "My order was supposed to arrive three days ago and tracking hasn't moved since it left the warehouse, can someone check on this?", "tag": "order_delay"},
    {"text": "THIS IS ABSOLUTELY RIDICULOUS. I received someone else's package instead of mine and support keeps giving me the runaround!!!", "tag": "order_angry"},
    {"text": "cancel my order NOW. it's been stuck in processing for a week and I want a refund immediately", "tag": "order_urgent_refund"},

    # Payments & Billing Team (category: Payments & Refunds) / Returns & Refunds Team (category: Returns & Replacements)
    {"text": "Why is my refund for a returned item taking so long to process? Is this normal?", "tag": "refund_slow_confused"},
    {"text": "I was charged the full price even though I applied a 20% off coupon at checkout, can someone check this?", "tag": "payment_coupon_neutral"},
    {"text": "I want to exchange this foundation for a lighter shade but the return portal keeps saying my order isn't eligible.", "tag": "returns_exchange_frustrated"},
    {"text": "our corporate account's bulk return request for mismatched shade shipments has been pending review for two weeks, this is blocking restocking for a client event", "tag": "returns_urgent"},

    # Product Quality Team (category: Product Quality & Safety)
    {"text": "This is ridiculous!! The 'long-lasting' lipstick I bought fades within an hour every single time!!!", "tag": "quality_cosmetic_angry"},
    {"text": "The face cream gave my daughter a rash within a day of using it, and the safety seal looked already broken when it arrived.", "tag": "quality_safety_worried"},
    {"text": "I am so frustrated - every bottle of this serum I've bought in the last three months has smelled slightly different, this has happened four times now.", "tag": "quality_frustrated"},
    {"text": "The product I received expired two months ago according to the batch code. Is this safe to use at all?", "tag": "quality_expired_worried"},

    # Technical Support Team (category: App/Website Issue)
    {"text": "I can't get past the payment page, it just keeps spinning and never completes my order.", "tag": "app_checkout_confused"},
    {"text": "The app crashes every single time I try to open my wishlist. This has been happening since the last update.", "tag": "app_crash"},

    # Account & Loyalty Team (category: Account Access)
    {"text": "I can't log into my account, it says my password is incorrect but I know it's right.", "tag": "account_login_confused"},
    {"text": "I'm locked out of my account right before a big sale starts, please help urgently!", "tag": "account_locked_urgent"},
    {"text": "My OTP codes stopped arriving by SMS a couple days ago, can you check what's going on?", "tag": "account_otp_neutral"},

    # Triage (category: Seller/Vendor Issue — no dedicated vendor team)
    {"text": "The third-party seller for this item hasn't responded to my message in five days about a missing accessory.", "tag": "seller_unresponsive"},
    {"text": "Can you confirm if this seller is an authorized retailer for this brand? Something about the listing photos looks off.", "tag": "seller_listing_neutral"},

    # Triage (category: General Inquiry)
    {"text": "This is the third time I'm writing about the same refund issue and no one has responded. I am extremely frustrated at this point.", "tag": "complaint_repeat_frustrated"},
    {"text": "Oh great, ANOTHER delayed restock notification. Third time this month. Really building my confidence in this app.", "tag": "sarcasm"},
    {"text": "What are your customer service hours on weekends?", "tag": "general_hours"},
    {"text": "I've noticed response times from support have gotten noticeably slower over the past month compared to before, just wanted to flag it.", "tag": "complaint_slow_support"},
    {"text": "Just wanted to say the new packaging redesign is beautiful, really elevated the unboxing experience. Thanks team!", "tag": "general_positive"},

    # Product Quality Team (category: Product Quality & Safety, safety/authenticity escalation)
    {"text": "I noticed the tamper seal on my order was already broken when it arrived, is my product still safe to use?", "tag": "safety_broken_seal_worried"},
    {"text": "I think this palette might be counterfeit — the box print quality looks noticeably different from the one I bought in-store last year.", "tag": "safety_counterfeit_worried"},

    # Triage (very short / near-empty, ambiguous by design)
    {"text": "Help.", "tag": "very_short"},
    {"text": "??", "tag": "very_short"},
    {"text": "hey", "tag": "very_short"},

    # Ambiguous / multi-issue curveballs
    {"text": "Not sure where this goes but my order is late, my invoice looks wrong, and also is there a way to track multiple orders at once?", "tag": "ambiguous"},
    {"text": "I think I was overcharged but honestly I'm also having trouble understanding my invoice at all, could someone explain it and also check the amount?", "tag": "ambiguous"},
]
