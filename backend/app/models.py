from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class Category(str, Enum):
    ORDER_ISSUE = "Order Issue"
    PAYMENTS_REFUNDS = "Payments & Refunds"
    RETURNS_REPLACEMENTS = "Returns & Replacements"
    PRODUCT_QUALITY_SAFETY = "Product Quality & Safety"
    APP_WEBSITE_ISSUE = "App/Website Issue"
    ACCOUNT_ACCESS = "Account Access"
    SELLER_VENDOR_ISSUE = "Seller/Vendor Issue"
    GENERAL_INQUIRY = "General Inquiry"


class Priority(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class Team(str, Enum):
    TRIAGE = "Triage"
    ORDER_DELIVERY_TEAM = "Order & Delivery Team"
    RETURNS_REFUNDS_TEAM = "Returns & Refunds Team"
    PAYMENTS_BILLING_TEAM = "Payments & Billing Team"
    PRODUCT_QUALITY_TEAM = "Product Quality Team"
    TECHNICAL_SUPPORT_TEAM = "Technical Support Team"
    ACCOUNT_LOYALTY_TEAM = "Account & Loyalty Team"


class Tone(str, Enum):
    NEUTRAL = "neutral"
    FRUSTRATED = "frustrated"
    ANGRY = "angry"
    URGENT = "urgent"
    CONFUSED = "confused"
    WORRIED = "worried"
    POSITIVE = "positive"


class TicketStatus(str, Enum):
    NEW = "New"
    ROUTED = "Routed"
    IN_PROGRESS = "In Progress"
    RESOLVED = "Resolved"


class FeedbackSourceType(str, Enum):
    TICKET = "ticket"
    REVIEW = "review"
    SURVEY = "survey"


class SentimentLabel(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class FeedbackCategory(str, Enum):
    """The fixed, closed top-level taxonomy every piece of feedback is
    bucketed into. Distinct from the finer-grained `theme` field on
    FeedbackAnalysis (a sub-topic within a category, e.g. "Broken Seal"
    under PACKAGING_DAMAGE) — category is a closed set an LLM's structured
    output can strictly enforce; theme is closer to open vocabulary (see
    CATEGORY_THEMES below). GENERAL_PRAISE_OTHER is a deliberate escape
    valve for blank/near-empty/no-specific-topic input, not a 11th "real"
    category — see feedback_ai.SYSTEM_PROMPT for when it's used. Not to be
    confused with the unrelated `Category` enum above, which drives ticket
    routing."""

    PRODUCT_QUALITY_FIT = "Product Quality & Fit"
    PACKAGING_DAMAGE = "Packaging & Damage"
    DELIVERY_LOGISTICS = "Delivery & Logistics"
    REVIEW_APP_FLOW_FRICTION = "Review & App Flow Friction"
    AUTHENTICITY_TRUST = "Authenticity & Trust"
    PERSONALIZATION_MISMATCH = "Personalization Mismatch"
    PRICING_OFFERS = "Pricing & Offers"
    REWARDS_LOYALTY = "Rewards & Loyalty"
    CUSTOMER_SUPPORT = "Customer Support"
    GENERAL_PRAISE_OTHER = "General Praise / Other"


# Reference sub-themes per category — feedback_ai's classifier is guided
# toward these but may coin a new theme when nothing here fits well (theme
# is a plain string field on FeedbackAnalysis, not a closed enum, precisely
# to allow that escape hatch).
CATEGORY_THEMES: dict[str, list[str]] = {
    FeedbackCategory.PRODUCT_QUALITY_FIT.value: [
        "Didn't Suit Skin Type", "Wrong Shade", "Poor Fragrance", "Short Shelf Life",
        "Inconsistent Quality", "Formula Issue",
    ],
    FeedbackCategory.PACKAGING_DAMAGE.value: [
        "Leaked in Transit", "Broken Seal", "Tampered Packaging", "Cracked Container",
        "Missing Item in Box",
    ],
    FeedbackCategory.DELIVERY_LOGISTICS.value: [
        "Late Delivery", "Wrong Item Shipped", "Non-Delivery", "Courier Behaviour",
        "Lost Package",
    ],
    FeedbackCategory.REVIEW_APP_FLOW_FRICTION.value: [
        "Rating Reset Mid-Order", "Forced Fields", "Redundant Re-selection",
        "App Crash", "Checkout Bug", "Slow Loading",
    ],
    FeedbackCategory.AUTHENTICITY_TRUST.value: [
        "Suspected Counterfeit", "Missing Seal", "Ingredient Mismatch",
    ],
    FeedbackCategory.PERSONALIZATION_MISMATCH.value: [
        "Beauty Portfolio Mismatch", "Irrelevant Recommendation", "Shade Finder Inaccurate",
    ],
    FeedbackCategory.PRICING_OFFERS.value: [
        "Coupon Not Applied", "Price Drop After Purchase", "Hidden Charges", "Refund Delay",
    ],
    FeedbackCategory.REWARDS_LOYALTY.value: [
        "Points Not Credited", "Moderation Delay", "Tier Benefits Unclear",
    ],
    FeedbackCategory.CUSTOMER_SUPPORT.value: [
        "Slow Response", "Unhelpful Agent", "Helpful Support", "Ticket Resolution",
    ],
    FeedbackCategory.GENERAL_PRAISE_OTHER.value: [
        "Overall Satisfaction", "Great Product", "Reliable Brand",
        "General Comments", "Mixed Feedback", "Spam", "Insufficient Detail", "Unclassified",
    ],
}


class TicketClassification(BaseModel):
    """Schema Claude must fill in exactly — enforced via output_config.format."""

    category: Category
    priority: Priority
    team: Team
    tone: Tone
    confidence: float = Field(ge=0, le=1, description="0-1 confidence in this classification")
    is_ambiguous: bool = Field(description="True if the ticket could reasonably fit more than one category")
    reasoning: str = Field(description="One-line explanation of the routing decision")


class FeedbackAnalysis(BaseModel):
    """Schema the model must fill in for the PM insights pipeline — a
    different lens on customer voice than TicketClassification, which is
    about routing. This is about what the feedback says: how the customer
    feels, what it's about, how urgent it is, and whether it actually needs
    a human to act on it at all."""

    sentiment_label: SentimentLabel
    sentiment_score: float = Field(ge=-1, le=1, description="-1 (very negative) to 1 (very positive)")
    category: FeedbackCategory = Field(description="The single fixed top-level category this feedback belongs to")
    theme: str = Field(
        min_length=1, max_length=80,
        description="A specific sub-topic within category — prefer one of CATEGORY_THEMES[category], "
        "but a new concise theme name is fine when nothing there fits",
    )
    urgency_score: float = Field(ge=0, le=1, description="0 (no urgency) to 1 (needs immediate attention)")
    is_actionable_ticket: bool = Field(
        description="True if this genuinely needs a human/team to act on it as a support issue; "
        "False if it's venting, praise, or general commentary with nothing to act on"
    )
    reasoning: str = Field(description="One-line explanation, specific to this item's content")


class RecommendedActionItem(BaseModel):
    category: str
    action_text: str = Field(min_length=1, max_length=300, description="One concrete, specific action a product/CX team could take")
    rationale: str = Field(min_length=1, max_length=300, description="Why this action, citing the specific trend/urgency/sentiment numbers given")


class RecommendedActionsResult(BaseModel):
    actions: list[RecommendedActionItem] = Field(max_length=10)


class ActionStatusUpdateRequest(BaseModel):
    status: str = Field(pattern="^(pending|done)$")


class NarrativeReport(BaseModel):
    """The plain-language periodic report — meant to be read by a
    non-technical manager, not an analyst: a short, scannable list of bullet
    points per field rather than paragraphs, still deliberately not a
    data-report shape (no headline/stat-citations)."""

    narrative: list[str] = Field(min_length=1, max_length=5, description="2-4 short bullet points telling the story of this period, like briefing someone non-technical out loud")
    whats_going_well: list[str] = Field(min_length=1, max_length=4, description="1-3 short bullet points on what's working, in plain language")
    top_pain_point: list[str] = Field(min_length=1, max_length=4, description="1-3 short bullet points naming the biggest complaint(s)/concern(s), in plain language")
    recommendation: list[str] = Field(min_length=1, max_length=4, description="1-3 short bullet points on what to do about it, in plain language")


class ResolutionSuggestion(BaseModel):
    """Schema the model must fill in for the customer-facing self-service
    suggestion shown before a ticket is ever created — a different shape
    from TicketClassification since this isn't a routing decision."""

    can_likely_self_resolve: bool
    summary: str = Field(description="One short sentence naming the likely underlying issue")
    steps: list[str] = Field(max_length=6, description="Concrete steps the customer can try themselves")


class RouteRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    manual_time_seconds: Optional[float] = Field(default=None, description="Real measured time a human took to triage this ticket, if available")
    compare: bool = Field(default=False, description="Also run the naive keyword baseline for side-by-side comparison")


class BaselineResult(BaseModel):
    category: Category
    priority: Priority
    team: Team
    reasoning: str


class ModelResult(BaseModel):
    """One provider's answer for a ticket, used when multiple live providers
    are configured and compare=True — shown side by side in the UI."""

    provider: str
    model_used: str
    mode: str
    latency_ms: int
    category: Category
    priority: Priority
    team: Team
    tone: Tone
    confidence: float
    is_ambiguous: bool
    reasoning: str


class TicketResult(BaseModel):
    id: int
    user_id: Optional[int] = None
    message: str
    status: TicketStatus = TicketStatus.NEW
    # Unset until an Admin routes the ticket (status moves New -> Routed).
    category: Optional[Category] = None
    priority: Optional[Priority] = None
    team: Optional[Team] = None
    tone: Optional[Tone] = None
    confidence: Optional[float] = None
    is_ambiguous: Optional[bool] = None
    escalated: Optional[bool] = None
    reasoning: Optional[str] = None
    model_used: Optional[str] = None
    mode: Optional[str] = None  # "live" | "mock" | "repaired" | "fallback"
    latency_ms: Optional[int] = None
    manual_time_seconds: Optional[float] = None
    created_at: str
    baseline: Optional[BaselineResult] = None
    model_results: Optional[list[ModelResult]] = None
    corrected_category: Optional[Category] = None
    corrected_priority: Optional[Priority] = None
    corrected_team: Optional[Team] = None
    feedback_note: Optional[str] = None


class SignupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=6, max_length=200)


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    role: str  # "user" | "team" | "admin" | "pm" | "dev"
    name: str
    team: Optional[Team] = None


class TeamMemberCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=6, max_length=200)
    team: Team


class ForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=3, max_length=200)


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=6, max_length=200)


class NewTicketRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)


class FeedbackImportRequest(BaseModel):
    """PM-side batch import for customer voice that has no other way into
    this app — external reviews or survey exports pasted in one go, one
    item per line. Tickets are never imported this way; they arrive
    automatically via ticket creation."""

    source_type: FeedbackSourceType
    items: list[str] = Field(min_length=1, max_length=500)

    @field_validator("source_type")
    @classmethod
    def _not_ticket(cls, v: FeedbackSourceType) -> FeedbackSourceType:
        if v == FeedbackSourceType.TICKET:
            raise ValueError("tickets are ingested automatically, not imported")
        return v


class SurveyRequest(BaseModel):
    """A customer's quick CSAT-style survey response — always analyzed by
    feedback_ai and logged to feedback_items, entirely separate from the
    ticket lifecycle (no team, no status, nothing to route)."""

    rating: int = Field(ge=1, le=5, description="1 (very unhappy) to 5 (very happy)")
    comment: Optional[str] = Field(default=None, max_length=2000)


class SelfResolvedRequest(BaseModel):
    """Logged when a customer confirms the AI's self-service suggestion
    solved their issue — no ticket is ever created for these, but an Admin
    can still see that AI handled it."""

    message: str = Field(min_length=1, max_length=8000)
    summary: Optional[str] = Field(default=None, max_length=500)
    steps: list[str] = Field(default_factory=list, max_length=6)


class TicketStatusUpdateRequest(BaseModel):
    status: TicketStatus


class TicketCommentRequest(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class AdminAssignRequest(BaseModel):
    """What an Admin confirms a previewed ticket with. The earlier preview
    call (POST .../route) never writes to the ticket — this is what actually
    moves it to Routed, so a ticket left unconfirmed stays untouched even
    after the AI's pick has been previewed on screen. category/priority/team
    default to whatever the AI suggested but the admin can override any of
    them; the rest of the fields carry the classification exactly as
    reviewed, since this call persists it in one shot rather than re-running
    the classifier."""

    category: Category
    priority: Priority
    team: Team
    tone: Tone
    confidence: float = Field(ge=0, le=1)
    is_ambiguous: bool
    escalated: bool
    reasoning: str
    model_used: str
    mode: str
    latency_ms: int
    baseline: Optional[BaselineResult] = None
    model_results: Optional[list[ModelResult]] = None


class FeedbackRequest(BaseModel):
    agree: bool = Field(description="True if a human reviewed this and confirmed the AI got it right")
    corrected_category: Optional[Category] = None
    corrected_priority: Optional[Priority] = None
    corrected_team: Optional[Team] = None
    note: Optional[str] = Field(default=None, max_length=500)


class DemoRunRequest(BaseModel):
    tickets: list[str] = Field(min_length=1, max_length=100)


# ---- PM-authored custom surveys ------------------------------------------

# Every custom survey uses this exact 5-point scale — deliberately not a
# PM choice: 1/2 are the negative zone ("Worst"/"Bad" — distinct severities
# of dissatisfaction), 3 is the true neutral midpoint, 4/5 are the positive
# zone. See main.py's _survey_response_type for the matching classification.
SURVEY_SCALE_POINTS = 5
SURVEY_SCALE_LABELS: list[str] = ["Worst", "Bad", "Okay", "Good", "Best"]


class CustomSurveyCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    questions: list[str] = Field(min_length=1, max_length=10)

    @field_validator("questions")
    @classmethod
    def _no_blank_questions(cls, v: list[str]) -> list[str]:
        cleaned = [q.strip() for q in v if q.strip()]
        if not cleaned:
            raise ValueError("at least one non-blank question is required")
        return cleaned


class SurveyAnswerRequest(BaseModel):
    answers: list[int] = Field(min_length=1, max_length=10)
