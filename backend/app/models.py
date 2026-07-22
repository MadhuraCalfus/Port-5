from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class Category(str, Enum):
    BILLING = "Billing"
    TECHNICAL_ISSUE = "Technical Issue"
    ACCOUNT_ACCESS = "Account Access"
    BUG_REPORT = "Bug Report"
    FEATURE_REQUEST = "Feature Request"
    COMPLAINT = "Complaint"
    SECURITY_CONCERN = "Security Concern"
    GENERAL_INQUIRY = "General Inquiry"


class Priority(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class Team(str, Enum):
    BILLING_SUPPORT = "Billing Support"
    TECHNICAL_SUPPORT = "Technical Support"
    ENGINEERING = "Engineering"
    ACCOUNT_MANAGEMENT = "Account Management"
    PRODUCT_TEAM = "Product Team"
    SECURITY_TEAM = "Security Team"
    CUSTOMER_SUCCESS = "Customer Success"
    TRIAGE = "Triage"


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
    MIXED = "mixed"


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
    theme: str = Field(
        min_length=1,
        max_length=80,
        description="A short, specific label for the underlying topic (e.g. 'checkout latency', "
        "'duplicate billing charge') — never a generic bucket like 'customer issues' or 'bad experience'",
    )
    urgency_score: float = Field(ge=0, le=1, description="0 (no urgency) to 1 (needs immediate attention)")
    is_actionable_ticket: bool = Field(
        description="True if this genuinely needs a human/team to act on it as a support issue; "
        "False if it's venting, praise, or general commentary with nothing to act on"
    )
    reasoning: str = Field(description="One-line explanation, specific to this item's content")


class RecommendedActionItem(BaseModel):
    theme: str
    action_text: str = Field(min_length=1, max_length=300, description="One concrete, specific action a product/CX team could take")
    rationale: str = Field(min_length=1, max_length=300, description="Why this action, citing the specific trend/urgency/sentiment numbers given")


class RecommendedActionsResult(BaseModel):
    actions: list[RecommendedActionItem] = Field(max_length=10)


class ActionStatusUpdateRequest(BaseModel):
    status: str = Field(pattern="^(pending|done)$")


class NarrativeReport(BaseModel):
    """The plain-language periodic report — meant to be readable by anyone,
    not just the PM who generated it (a VP of CX, an exec skimming a
    deck)."""

    headline: str = Field(min_length=1, max_length=140, description="One sentence: the single most important thing that happened this period")
    key_findings: list[str] = Field(min_length=1, max_length=6, description="3-6 short, specific findings — not generic filler")
    narrative: str = Field(min_length=1, max_length=1200, description="A short plain-language paragraph explaining what happened and why it matters")
    bottom_line: str = Field(min_length=1, max_length=300, description="The single most actionable takeaway — what to do first")


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
    role: str  # "user" | "team" | "admin" | "pm"
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
