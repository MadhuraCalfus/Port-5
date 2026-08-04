import os
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from fastapi import Depends, FastAPI, File, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import actions_ai, analytics, auth, classifier, email_service, feedback_ai, insights, narrative_ai, store, ticket_report
from . import nykaa_seed, nykaa_store
from .nykaa_routes import nykaa_router
from .models import (
    ActionStatusUpdateRequest,
    AdminAssignRequest,
    CustomSurveyCreateRequest,
    DemoRunRequest,
    FeedbackImportRequest,
    FeedbackRequest,
    ForgotPasswordRequest,
    LoginRequest,
    NewTicketRequest,
    ResetPasswordRequest,
    RouteRequest,
    SelfResolvedRequest,
    SignupRequest,
    SurveyAnswerRequest,
    SurveyRequest,
    SURVEY_SCALE_LABELS,
    SURVEY_SCALE_POINTS,
    TeamMemberCreateRequest,
    TicketCommentRequest,
    TicketStatusUpdateRequest,
    TokenResponse,
)
from .sample_tickets import SAMPLE_TICKETS

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")
RESET_TOKEN_MINUTES = 30

# ---- ticket attachments (customer/team file uploads in a ticket's chat) --
ALLOWED_ATTACHMENT_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "application/pdf", "text/plain", "text/csv",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024  # 5MB

app = FastAPI(title="NykaaPulse", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _no_cache(request, call_next):
    """These dashboards need every refresh to hit real, current data — never
    a cached copy of a previous response, whether from the browser or an
    intermediate proxy."""
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.on_event("startup")
def _startup():
    store.init_db()
    nykaa_store.init_nykaa_db()
    nykaa_seed.seed_catalog()


app.include_router(nykaa_router)


@app.get("/api/health")
def health():
    info = classifier.mode_info()
    return {"status": "ok", **info, "ticket_count": store.count_tickets()}


# ---- auth -------------------------------------------------------------

@app.post("/api/auth/signup", response_model=TokenResponse)
def signup(req: SignupRequest):
    if store.get_user_by_email(req.email):
        raise HTTPException(status_code=409, detail="an account with that email already exists")
    user = store.create_user(req.name, req.email, auth.hash_password(req.password))
    token = auth.create_token(user["id"], "user", user["name"])
    return TokenResponse(access_token=token, role="user", name=user["name"])


@app.post("/api/auth/login", response_model=TokenResponse)
def login(req: LoginRequest):
    user = store.get_user_by_email(req.email)
    if user and auth.verify_password(req.password, user["password_hash"]):
        token = auth.create_token(user["id"], "user", user["name"])
        return TokenResponse(access_token=token, role="user", name=user["name"])

    member = store.get_team_member_by_email(req.email)
    if member and auth.verify_password(req.password, member["password_hash"]):
        token = auth.create_token(member["id"], "team", member["name"], team=member["team"])
        return TokenResponse(access_token=token, role="team", name=member["name"], team=member["team"])

    if req.email == auth.ADMIN_EMAIL and req.password == auth.ADMIN_PASSWORD:
        token = auth.create_token("admin", "admin", "Admin")
        return TokenResponse(access_token=token, role="admin", name="Admin")

    if req.email == auth.PM_EMAIL and req.password == auth.PM_PASSWORD:
        token = auth.create_token("pm", "pm", "Product Manager")
        return TokenResponse(access_token=token, role="pm", name="Product Manager")

    raise HTTPException(status_code=401, detail="invalid email or password")


@app.get("/api/auth/me")
def me(claims: dict = Depends(auth.require_any)):
    return claims


@app.post("/api/auth/forgot-password")
def forgot_password(req: ForgotPasswordRequest):
    """Team-lead self-service reset. Always returns the same generic message
    whether or not the email exists, so this can't be used to enumerate
    which addresses have accounts."""
    member = store.get_team_member_by_email(req.email)
    if member:
        token = auth.generate_reset_token()
        expires = (datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_MINUTES)).isoformat()
        store.set_team_member_reset_token(member["id"], token, expires)
        reset_link = f"{FRONTEND_URL}/reset-password?token={token}"
        email_service.send_email(
            member["email"],
            "Reset your NykaaPulse password",
            f"Hi {member['name']},\n\nClick the link below to set a new password. "
            f"This link expires in {RESET_TOKEN_MINUTES} minutes.\n\n{reset_link}\n\n"
            "If you didn't request this, you can ignore this email.",
        )
    return {"message": "if that email has an account, a reset link has been sent"}


@app.post("/api/auth/reset-password")
def reset_password(req: ResetPasswordRequest):
    member = store.get_team_member_by_reset_token(req.token)
    if not member or not member["reset_token_expires"]:
        raise HTTPException(status_code=400, detail="invalid or expired reset link")
    if datetime.fromisoformat(member["reset_token_expires"]) < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="invalid or expired reset link")
    store.update_team_member_password(member["id"], auth.hash_password(req.new_password))
    store.clear_team_member_reset_token(member["id"])
    return {"message": "password updated"}


# ---- admin sandbox tools (Manual vs AI Race / Demo / Analytics) ----
# Gated behind admin login. Race and Demo classify ad-hoc/sample text for
# demonstration purposes only — deliberately NOT persisted, so they never
# show up in All Tickets, Analytics, or the Teams summary.

@app.post("/api/route")
def route_ticket(req: RouteRequest, claims: dict = Depends(auth.require_admin)):
    return classifier.build_ticket_result(req.message, req.manual_time_seconds, req.compare)


@app.get("/api/tickets")
def get_tickets(limit: int = 50, offset: int = 0, claims: dict = Depends(auth.require_admin)):
    return {"tickets": store.list_tickets(limit=limit, offset=offset), "total": store.count_tickets()}


@app.get("/api/tickets/{ticket_id}")
def get_ticket(ticket_id: int, claims: dict = Depends(auth.require_admin)):
    t = store.get_ticket(ticket_id)
    if not t:
        raise HTTPException(status_code=404, detail="ticket not found")
    return t


@app.post("/api/tickets/{ticket_id}/feedback")
def give_feedback(ticket_id: int, req: FeedbackRequest, claims: dict = Depends(auth.require_admin)):
    existing = store.get_ticket(ticket_id)
    if not existing:
        raise HTTPException(status_code=404, detail="ticket not found")
    updated = store.save_feedback(
        ticket_id,
        req.corrected_category.value if req.corrected_category else None,
        req.corrected_priority.value if req.corrected_priority else None,
        req.corrected_team.value if req.corrected_team else None,
        req.note,
    )
    return updated


# ---- user: submit + track tickets --------------------------------------

@app.post("/api/tickets/suggest")
def suggest_ticket_resolution(req: NewTicketRequest, claims: dict = Depends(auth.require_user)):
    """Self-service first step, before any ticket exists — not persisted, not
    routed. If the customer says it didn't help, they hit "raise a ticket"
    next, which is what actually calls create_ticket below. If it did help,
    the frontend calls mark_self_resolved instead — so an Admin can still see
    that AI closed it out, even though no ticket/team was ever involved."""
    return classifier.suggest_resolution(req.message)


@app.post("/api/tickets/self-resolved")
def mark_self_resolved(req: SelfResolvedRequest, claims: dict = Depends(auth.require_user)):
    """The customer confirmed the AI's suggestion above actually solved it —
    logged so an Admin can see AI deflections alongside real tickets, without
    this ever becoming a ticket or touching a team's queue."""
    return store.save_self_resolved(int(claims["sub"]), req.message, req.summary, req.steps)


def _analyze_and_log_feedback(
    source_type: str, text: str, source_ref: int | None = None, user_id: int | None = None, rating: int | None = None
) -> None:
    """Run the PM insights pipeline on one piece of customer voice and log
    it to feedback_items — shared by every ingestion path (ticket creation,
    survey submission, and review import) so they all feed the same unified
    table the same way. user_id is set for tickets/surveys (a real account
    is always behind them) and left unset for imported reviews, which have
    no account behind them at all. rating is only ever set for surveys —
    tickets/reviews have no star rating to attach."""
    outcome = feedback_ai.analyze_feedback(text)
    a = outcome.analysis
    # A 1-2 star rating is an unambiguous, deterministic urgency signal —
    # applied as a floor rather than left to the AI's judgment, since it's a
    # plain fact (not something needing interpretation) and this session
    # already found LLM prompt-nudges unreliable for a similarly narrow rule.
    urgency_score = max(a.urgency_score, 0.5) if rating is not None and rating <= 2 else a.urgency_score
    store.save_feedback_item(
        source_type=source_type,
        source_ref=source_ref,
        user_id=user_id,
        rating=rating,
        text=text,
        sentiment_label=a.sentiment_label.value,
        sentiment_score=a.sentiment_score,
        category=a.category.value,
        theme=a.theme,
        urgency_score=urgency_score,
        is_actionable_ticket=a.is_actionable_ticket,
        model_used=outcome.model_used,
        mode=outcome.mode,
        latency_ms=outcome.latency_ms,
    )


@app.post("/api/tickets")
def create_ticket(req: NewTicketRequest, claims: dict = Depends(auth.require_user)):
    """A user submits a ticket. No routing AI call here — it stays
    unclassified (status="New") until an Admin routes it. It does, however,
    get mirrored into feedback_items right away: the PM insights pipeline
    (sentiment/category/theme/urgency) runs independently of routing, on its own
    timeline, without waiting on an Admin to ever pick this ticket up."""
    ticket = store.create_ticket(user_id=int(claims["sub"]), message=req.message)
    _analyze_and_log_feedback("ticket", req.message, source_ref=ticket["id"], user_id=int(claims["sub"]))
    return ticket


@app.post("/api/surveys")
def submit_survey(req: SurveyRequest, claims: dict = Depends(auth.require_user)):
    """A quick CSAT-style survey response — entirely separate from the
    ticket lifecycle (no team, no status, nothing to route). Always logged
    to feedback_items for the PM dashboard; there is no other consumer of
    this data, so there's nothing to return beyond an acknowledgement.

    Analyzes and stores just the customer's own comment — `rating` already
    has its own column, so it doesn't need to be embedded in the text a PM
    reads in All Feedback or the text the AI classifier itself analyzes."""
    text = req.comment.strip() if req.comment and req.comment.strip() else "(No comment provided — survey rating only)"
    _analyze_and_log_feedback("survey", text, user_id=int(claims["sub"]), rating=req.rating)
    return {"message": "thank you for your feedback"}


@app.get("/api/my-tickets")
def my_tickets(claims: dict = Depends(auth.require_user)):
    tickets = store.list_tickets_for_user(int(claims["sub"]))
    unread = store.unread_comment_counts([t["id"] for t in tickets], "user", str(claims["sub"]))
    for t in tickets:
        t["unread_comments"] = unread.get(t["id"], 0)
    return {"tickets": tickets}


@app.get("/api/my-self-resolved")
def my_self_resolved(claims: dict = Depends(auth.require_user)):
    """A customer's own history of issues AI resolved before they ever
    became a ticket — the self-service mirror of my_tickets above."""
    return {"cases": store.list_self_resolved_for_user(int(claims["sub"]))}


# ---- admin: route the queue + full detail ------------------------------

@app.get("/api/admin/tickets/new")
def admin_new_tickets(claims: dict = Depends(auth.require_admin)):
    return {"tickets": store.list_tickets_by_status("New")}


@app.post("/api/admin/tickets/{ticket_id}/route")
def admin_route_ticket(ticket_id: int, claims: dict = Depends(auth.require_admin)):
    """Preview only — classifies the ticket and returns the AI's pick.
    Nothing is written to the ticket here: leaving the New Tickets queue
    without hitting Confirm Route leaves it exactly as it was (status New,
    unassigned). Confirm Route (admin_assign_ticket below) is the only call
    that actually persists anything."""
    ticket = store.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="ticket not found")
    # compare=True so the admin sees the same full picture as the Route a
    # Ticket tab (baseline + multi-model comparison), not just the bare pick.
    return classifier.build_ticket_result(ticket["message"], manual_time_seconds=None, compare=True)


@app.post("/api/admin/tickets/{ticket_id}/assign")
def admin_assign_ticket(ticket_id: int, req: AdminAssignRequest, claims: dict = Depends(auth.require_admin)):
    """Confirm Route: the only call that actually moves a ticket from New to
    Routed. Persists category/priority/team (the AI's pick, or the admin's
    override) plus the rest of the classification exactly as previewed,
    rather than re-running the classifier and risking a different result
    than what was reviewed on screen."""
    ticket = store.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="ticket not found")
    result = {
        "category": req.category.value,
        "priority": req.priority.value,
        "team": req.team.value,
        "tone": req.tone.value,
        "confidence": req.confidence,
        "is_ambiguous": req.is_ambiguous,
        "escalated": req.escalated,
        "reasoning": req.reasoning,
        "model_used": req.model_used,
        "mode": req.mode,
        "latency_ms": req.latency_ms,
        "baseline": req.baseline.model_dump() if req.baseline else None,
        "model_results": [m.model_dump() for m in req.model_results] if req.model_results else None,
    }
    return store.apply_classification(ticket_id, result)


@app.get("/api/admin/tickets")
def admin_all_tickets(claims: dict = Depends(auth.require_admin)):
    return {"tickets": store.list_tickets_with_user(), "total": store.count_tickets()}


@app.get("/api/admin/self-resolved")
def admin_self_resolved(claims: dict = Depends(auth.require_admin)):
    """Every case where AI's self-service suggestion solved the customer's
    issue before a ticket ever existed — visibility into deflected volume
    that otherwise wouldn't show up anywhere in the ticket queue."""
    return {"cases": store.list_self_resolved(), "total": store.count_self_resolved()}


@app.get("/api/admin/tickets/{ticket_id}/report.pdf")
def admin_ticket_report(ticket_id: int, claims: dict = Depends(auth.require_admin)):
    ticket = store.get_ticket_with_user(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="ticket not found")
    comments = store.list_ticket_comments_with_attachments(ticket_id)
    pdf_bytes = ticket_report.generate_ticket_report(ticket, comments)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="ticket-{ticket_id}-report.pdf"'},
    )


@app.get("/api/admin/team-summary")
def admin_team_summary(claims: dict = Depends(auth.require_admin)):
    return analytics.compute_team_summary()


@app.get("/api/admin/team-members")
def admin_list_team_members(claims: dict = Depends(auth.require_admin)):
    return {"team_members": store.list_team_members()}


@app.post("/api/admin/team-members")
def admin_create_team_member(req: TeamMemberCreateRequest, claims: dict = Depends(auth.require_admin)):
    if store.get_team_member_by_email(req.email):
        raise HTTPException(status_code=409, detail="an account with that email already exists")
    member = store.create_team_member(req.name, req.email, auth.hash_password(req.password), req.team.value)
    emailed = email_service.send_email(
        req.email,
        "Your NykaaPulse team account",
        f"Hi {req.name},\n\nAn account was created for you on the {req.team.value} team.\n\n"
        f"Email: {req.email}\nPassword: {req.password}\n\n"
        f"Log in at {FRONTEND_URL}/login and change your password any time via \"Forgot password?\".",
    )
    return {**member, "emailed": emailed}


@app.delete("/api/admin/team-members/{member_id}")
def admin_delete_team_member(member_id: int, claims: dict = Depends(auth.require_admin)):
    if not store.get_team_member_by_id(member_id):
        raise HTTPException(status_code=404, detail="team member not found")
    store.delete_team_member(member_id)
    return {"deleted": True}


# ---- team: work the assigned queue --------------------------------------

@app.get("/api/team/tickets")
def team_tickets(claims: dict = Depends(auth.require_team)):
    tickets = store.list_tickets_for_team(claims["team"])
    unread = store.unread_comment_counts([t["id"] for t in tickets], "team", claims["team"])
    for t in tickets:
        t["unread_comments"] = unread.get(t["id"], 0)
    return {"tickets": tickets}


# Status only ever moves forward — a team can't send a ticket back to an
# earlier stage (e.g. Resolved -> In Progress), even via a direct API call.
_ALLOWED_STATUS_MOVES = {
    "Routed": {"Routed", "In Progress", "Resolved"},
    "In Progress": {"In Progress", "Resolved"},
    "Resolved": {"Resolved"},
}


@app.patch("/api/team/tickets/{ticket_id}/status")
def team_update_status(ticket_id: int, req: TicketStatusUpdateRequest, claims: dict = Depends(auth.require_team)):
    ticket = store.get_ticket(ticket_id)
    if not ticket or ticket.get("team") != claims["team"]:
        raise HTTPException(status_code=404, detail="ticket not found")
    allowed = _ALLOWED_STATUS_MOVES.get(ticket["status"], set())
    if req.status.value not in allowed:
        raise HTTPException(status_code=400, detail=f"a {ticket['status']} ticket can't be moved back to {req.status.value}")
    return store.update_ticket_status(ticket_id, req.status.value)


# ---- ticket comments: customer <-> team messaging on one ticket --------
# Shared across roles, so it's gated by ownership checked in-handler rather
# than a single require_* dependency: a customer only sees their own
# ticket's thread, a team member only sees threads for tickets already
# routed to their team, and an admin can see any of them.

def _can_access_ticket_comments(ticket: dict, claims: dict) -> bool:
    role = claims["role"]
    if role == "admin":
        return True
    if role == "user":
        return ticket["user_id"] == int(claims["sub"])
    if role == "team":
        return ticket.get("team") == claims.get("team")
    return False


# Messaging only opens once a team is actively working the ticket, and
# locks again once it's resolved — reading old history is still fine after
# that (handled by _can_access_ticket_comments alone), only composing new
# messages/attachments requires the ticket to be "In Progress".
def _ticket_messaging_open(ticket: dict) -> bool:
    return ticket["status"] == "In Progress"


def _viewer_key(claims: dict) -> str | None:
    if claims["role"] == "user":
        return str(claims["sub"])
    if claims["role"] == "team":
        return claims["team"]
    return None


@app.get("/api/tickets/{ticket_id}/comments")
def get_ticket_comments(ticket_id: int, claims: dict = Depends(auth.require_any)):
    ticket = store.get_ticket(ticket_id)
    if not ticket or not _can_access_ticket_comments(ticket, claims):
        raise HTTPException(status_code=404, detail="ticket not found")
    return {"comments": store.list_ticket_comments(ticket_id), "messaging_open": _ticket_messaging_open(ticket)}


@app.post("/api/tickets/{ticket_id}/comments/read")
def mark_ticket_comments_read(ticket_id: int, claims: dict = Depends(auth.require_any)):
    ticket = store.get_ticket(ticket_id)
    if not ticket or not _can_access_ticket_comments(ticket, claims):
        raise HTTPException(status_code=404, detail="ticket not found")
    viewer_key = _viewer_key(claims)
    if viewer_key is not None:
        store.mark_comments_read(ticket_id, claims["role"], viewer_key)
    return {"marked_read": True}


@app.post("/api/tickets/{ticket_id}/comments")
def post_ticket_comment(ticket_id: int, req: TicketCommentRequest, claims: dict = Depends(auth.require_any)):
    ticket = store.get_ticket(ticket_id)
    if not ticket or not _can_access_ticket_comments(ticket, claims):
        raise HTTPException(status_code=404, detail="ticket not found")
    if not _ticket_messaging_open(ticket):
        raise HTTPException(status_code=400, detail="messaging is only available while a ticket is in progress")
    return store.add_ticket_comment(ticket_id, claims["role"], claims["name"], req.body)


@app.post("/api/tickets/{ticket_id}/attachments")
async def post_ticket_attachment(ticket_id: int, file: UploadFile = File(...), claims: dict = Depends(auth.require_any)):
    ticket = store.get_ticket(ticket_id)
    if not ticket or not _can_access_ticket_comments(ticket, claims):
        raise HTTPException(status_code=404, detail="ticket not found")
    if not _ticket_messaging_open(ticket):
        raise HTTPException(status_code=400, detail="messaging is only available while a ticket is in progress")
    if file.content_type not in ALLOWED_ATTACHMENT_TYPES:
        raise HTTPException(status_code=400, detail=f"unsupported file type: {file.content_type}")

    contents = await file.read()
    if len(contents) > MAX_ATTACHMENT_BYTES:
        raise HTTPException(status_code=400, detail="file too large (max 5MB)")

    return store.add_ticket_comment(
        ticket_id,
        claims["role"],
        claims["name"],
        body="",
        attachment_data=contents,
        attachment_name=file.filename or "attachment",
        attachment_mime=file.content_type,
    )


@app.get("/api/tickets/{ticket_id}/attachments/{comment_id}")
def get_ticket_attachment(ticket_id: int, comment_id: int, claims: dict = Depends(auth.require_any)):
    ticket = store.get_ticket(ticket_id)
    if not ticket or not _can_access_ticket_comments(ticket, claims):
        raise HTTPException(status_code=404, detail="ticket not found")
    comment = store.get_ticket_comment(comment_id)
    if not comment or comment["ticket_id"] != ticket_id or not comment["attachment_data"]:
        raise HTTPException(status_code=404, detail="attachment not found")
    safe_name = (comment["attachment_name"] or "attachment").replace('"', "").replace("\n", "").replace("\r", "")
    return Response(
        content=comment["attachment_data"],
        media_type=comment["attachment_mime"] or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


@app.get("/api/analytics")
def get_analytics(claims: dict = Depends(auth.require_admin)):
    return analytics.compute_analytics()


@app.get("/api/sample-tickets")
def get_sample_tickets(claims: dict = Depends(auth.require_admin)):
    return {"tickets": SAMPLE_TICKETS}


@app.post("/api/demo/run")
def run_demo(req: DemoRunRequest, claims: dict = Depends(auth.require_admin)):
    """Classify the sample tickets for demonstration only — not persisted,
    so the demo set never pollutes real ticket history/analytics."""
    results = [classifier.build_ticket_result(text, manual_time_seconds=None, compare=True) for text in req.tickets]
    return {"results": results}


@app.get("/api/demo/repair-example")
def repair_example(claims: dict = Depends(auth.require_admin)):
    """Deterministic proof that the JSON-repair path works, independent of
    any live model call — good for the 'what happens with malformed JSON'
    part of the demo."""
    broken_examples = [
        '```json\n{"category": "Payments & Refunds", "priority": "High", "team": "Payments & Billing Team", '
        '"tone": "angry", "confidence": 0.8, "is_ambiguous": false, "reasoning": "Double charge complaint.",}\n```',
        'Sure! Here is the classification: {"category": "App/Website Issue", "priority": "Medium", '
        '"team": "Technical Support Team", "tone": "frustrated", "confidence": 0.7, "is_ambiguous": false, '
        '"reasoning": "Checkout page crash reported."} Let me know if you need anything else.',
        '{"category": "Product Quality & Safety" "priority": "High" "team": "Product Quality Team"}',
    ]
    return {"examples": [classifier.repair_demo(e) for e in broken_examples]}


# ---- pm: feedback insights ------------------------------------------------

@app.post("/api/pm/feedback/import")
def pm_import_feedback(req: FeedbackImportRequest, claims: dict = Depends(auth.require_pm)):
    """Batch-import reviews/surveys pasted in one go — the only way this
    kind of customer voice gets into the system, since there's no other
    product surface for it. Blank lines are skipped rather than logged as
    empty feedback."""
    imported = 0
    for raw in req.items:
        text = raw.strip()
        if not text:
            continue
        _analyze_and_log_feedback(req.source_type.value, text)
        imported += 1
    return {"imported": imported, "skipped": len(req.items) - imported}


@app.get("/api/pm/feedback")
def pm_list_feedback(limit: int = 200, claims: dict = Depends(auth.require_pm)):
    return {"items": store.list_feedback_items(limit=limit)}


@app.get("/api/pm/insights")
def pm_insights(period_type: str = "weekly", period_key: str | None = None, claims: dict = Depends(auth.require_pm)):
    """Category frequency, sentiment distribution, and urgency ranking for
    one period (defaults to the current one). Pass period_key (e.g.
    "2026-W29") to look at a past period — compute_period_insights lists
    every period that actually has data in its own response."""
    if period_type not in insights.PERIOD_TYPES:
        raise HTTPException(status_code=400, detail=f"period_type must be one of {insights.PERIOD_TYPES}")
    return insights.compute_period_insights(period_type, period_key)


@app.get("/api/pm/insights/trend")
def pm_insights_trend(period_type: str = "weekly", period_key: str | None = None, claims: dict = Depends(auth.require_pm)):
    """Period-over-period % change per category, plus the raw current/
    previous aggregates it was computed from."""
    if period_type not in insights.PERIOD_TYPES:
        raise HTTPException(status_code=400, detail=f"period_type must be one of {insights.PERIOD_TYPES}")
    return insights.compute_trend(period_type, period_key)


@app.get("/api/pm/insights/sentiment-series")
def pm_sentiment_series(
    period_type: str = "weekly", num_periods: int = 8, end_period_key: str | None = None, claims: dict = Depends(auth.require_pm)
):
    """The num_periods periods ending at end_period_key (defaults to the
    current period), oldest first — powers the "over time" trend charts."""
    if period_type not in insights.PERIOD_TYPES:
        raise HTTPException(status_code=400, detail=f"period_type must be one of {insights.PERIOD_TYPES}")
    return {"series": insights.compute_sentiment_series(period_type, num_periods, end_period_key)}


@app.get("/api/pm/insights/items")
def pm_period_items(period_type: str = "weekly", period_key: str | None = None, claims: dict = Depends(auth.require_pm)):
    """Every raw feedback_items row in one period — the full underlying data
    behind a period's numbers, used by the PM's PDF/CSV export."""
    if period_type not in insights.PERIOD_TYPES:
        raise HTTPException(status_code=400, detail=f"period_type must be one of {insights.PERIOD_TYPES}")
    return {"items": insights.get_period_items(period_type, period_key)}


def _validate_date_range(start: str, end: str) -> None:
    try:
        datetime.strptime(start, "%Y-%m-%d")
        datetime.strptime(end, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="start/end must be YYYY-MM-DD")
    if start > end:
        raise HTTPException(status_code=400, detail="start must be on or before end")


@app.get("/api/pm/insights/range")
def pm_insights_range(start: str, end: str, claims: dict = Depends(auth.require_pm)):
    """Aggregate stats for an arbitrary custom date range — Analytics'
    calendar-range picker, parallel to pm_insights' fixed period buckets
    but with no "previous range" trend/delta concept (there's no natural
    "previous" for an arbitrary window)."""
    _validate_date_range(start, end)
    return insights.compute_range_insights(start, end)


@app.post("/api/pm/insights/actions/generate")
def pm_generate_actions(period_type: str = "weekly", period_key: str | None = None, claims: dict = Depends(auth.require_pm)):
    """Recommend actions for whatever categories are worsening or already
    urgent this period, and persist them. Safe to call repeatedly — it
    always appends fresh recommendations rather than overwriting, so
    re-running this after new feedback comes in doesn't erase what a PM
    already marked done on earlier recommendations for the same period."""
    if period_type not in insights.PERIOD_TYPES:
        raise HTTPException(status_code=400, detail=f"period_type must be one of {insights.PERIOD_TYPES}")
    trend = insights.compute_trend(period_type, period_key)
    recommended = actions_ai.recommend_actions(trend)
    saved = [
        store.save_recommended_action(
            period_type=trend["period_type"],
            period_key=trend["current_period_key"],
            category=a["category"],
            action_text=a["action_text"],
            rationale=a["rationale"],
        )
        for a in recommended
    ]
    return {"period_type": trend["period_type"], "period_key": trend["current_period_key"], "actions": saved}


@app.get("/api/pm/insights/actions")
def pm_list_actions(period_type: str = "weekly", period_key: str | None = None, claims: dict = Depends(auth.require_pm)):
    if period_type not in insights.PERIOD_TYPES:
        raise HTTPException(status_code=400, detail=f"period_type must be one of {insights.PERIOD_TYPES}")
    key = period_key or insights.current_period_key(period_type)
    return {"period_type": period_type, "period_key": key, "actions": store.list_recommended_actions(period_type, key)}


@app.patch("/api/pm/insights/actions/{action_id}")
def pm_update_action_status(action_id: int, req: ActionStatusUpdateRequest, claims: dict = Depends(auth.require_pm)):
    action = store.update_action_status(action_id, req.status)
    if not action:
        raise HTTPException(status_code=404, detail="action not found")
    return action


@app.post("/api/pm/insights/report/generate")
def pm_generate_report(period_type: str = "weekly", period_key: str | None = None, claims: dict = Depends(auth.require_pm)):
    """Generate (or regenerate) the plain-language report for one period and
    persist it — an upsert, so calling this again after new feedback comes
    in replaces the report rather than accumulating duplicates. Also links
    any recommended_actions already generated for this period that weren't
    yet linked to a report."""
    if period_type not in insights.PERIOD_TYPES:
        raise HTTPException(status_code=400, detail=f"period_type must be one of {insights.PERIOD_TYPES}")
    trend = insights.compute_trend(period_type, period_key)
    report, mode, model_used = narrative_ai.generate_report(trend)
    saved = store.upsert_periodic_insight(
        period_type=trend["period_type"],
        period_key=trend["current_period_key"],
        period_start=trend["current_period_start"],
        period_end=trend["current_period_end"],
        category_trend=trend["category_deltas"],
        sentiment_trend={
            "avg_sentiment_score": trend["current"]["avg_sentiment_score"],
            "avg_sentiment_score_delta": trend["avg_sentiment_score_delta"],
            "avg_urgency_score": trend["current"]["avg_urgency_score"],
            "avg_urgency_score_delta": trend["avg_urgency_score_delta"],
            "sentiment_distribution": trend["current"]["sentiment_distribution"],
        },
        narrative=report,
        model_used=model_used,
        mode=mode,
    )
    store.link_actions_to_insight(trend["period_type"], trend["current_period_key"], saved["id"])
    return saved



# The fields today's NarrativeReport model requires — a report generated
# under an earlier version of that schema (e.g. the old headline/
# key_findings/bottom_line shape) is missing these entirely, and would
# render as blank "What went well"/"Top pain point"/"Recommendation" cards
# on the frontend rather than raising an error, since JS just reads
# undefined for a missing key.
_CURRENT_NARRATIVE_FIELDS = {"narrative", "whats_going_well", "top_pain_point", "recommendation"}


@app.get("/api/pm/insights/report")
def pm_get_report(period_type: str = "weekly", period_key: str | None = None, claims: dict = Depends(auth.require_pm)):
    if period_type not in insights.PERIOD_TYPES:
        raise HTTPException(status_code=400, detail=f"period_type must be one of {insights.PERIOD_TYPES}")
    key = period_key or insights.current_period_key(period_type)
    report = store.get_periodic_insight(period_type, key)
    # A report from a since-changed schema is treated as if nothing were
    # generated yet, so the frontend's existing "no report? generate one"
    # flow transparently refreshes it in the current format — no separate
    # migration step, no manual "Regenerate" click needed.
    if not report or not _CURRENT_NARRATIVE_FIELDS.issubset(report["narrative"].keys()):
        raise HTTPException(status_code=404, detail="no report generated for this period yet")
    return report


# ---- pm: custom surveys (ad-hoc question sets, distinct from the fixed
# star-rating survey above) -------------------------------------------------

def _survey_response_type(value: int) -> str:
    """The fixed classification for the 5-point scale every survey uses:
    1-2 (Worst/Bad) is the negative zone, 3 (Okay) is the exact neutral
    midpoint, 4-5 (Good/Best) is the positive zone."""
    if value <= 2:
        return "negative"
    if value == 3:
        return "neutral"
    return "positive"


def _survey_summary_line(distribution: dict) -> str:
    """A 1-2 sentence, plain-language read on a positive/neutral/negative
    split — deliberately qualitative, not a numbers/percentages recap (the
    distribution itself already shows the numbers). Pure arithmetic, no LLM
    call, same proportion as insights.py's other deterministic dials."""
    pos, neu, neg = distribution.get("positive", 0), distribution.get("neutral", 0), distribution.get("negative", 0)
    total = pos + neu + neg
    if total == 0:
        return "No responses yet — check back once customers have answered."
    pos_ratio, neg_ratio = pos / total, neg / total
    if pos_ratio >= 0.6:
        return "Customers are largely happy here — responses lean strongly positive."
    if neg_ratio >= 0.6:
        return "Customers are largely unhappy here — this likely needs attention."
    if pos_ratio > neg_ratio:
        return "Feedback leans positive overall, though a fair number of customers aren't fully satisfied."
    if neg_ratio > pos_ratio:
        return "Feedback leans negative overall, with real room to improve."
    return "Feedback is evenly mixed — customers are split between happy and unhappy."


@app.post("/api/pm/surveys")
def pm_create_survey(req: CustomSurveyCreateRequest, claims: dict = Depends(auth.require_pm)):
    return store.create_custom_survey(req.title, SURVEY_SCALE_POINTS, req.questions, claims.get("name"))


@app.get("/api/pm/surveys")
def pm_list_surveys(claims: dict = Depends(auth.require_pm)):
    return {"surveys": store.list_custom_surveys(), "scale_labels": SURVEY_SCALE_LABELS}


@app.get("/api/pm/surveys/overview")
def pm_surveys_overview(claims: dict = Depends(auth.require_pm)):
    """Rolled up across every SENT survey — how many distinct customers
    have responded at all, response volume per survey, and one pooled
    positive/neutral/negative read, for the "All Surveys" view on Survey
    Analytics rather than one survey at a time."""
    surveys = [s for s in store.list_custom_surveys() if s["status"] == "sent"]
    per_survey = []
    type_counts = Counter()
    scale_counts = Counter()
    all_values = []
    respondents: set[int] = set()
    total_responses = 0
    for s in surveys:
        responses = store.list_survey_responses(s["id"])
        total_responses += len(responses)
        for r in responses:
            respondents.add(r["user_id"])
            for v in r["answers"]:
                type_counts[_survey_response_type(v)] += 1
                scale_counts[v] += 1
                all_values.append(v)
        per_survey.append({
            "id": s["id"], "title": s["title"], "response_count": len(responses), "scale_points": s["scale_points"],
        })

    response_distribution = {
        "positive": type_counts.get("positive", 0),
        "neutral": type_counts.get("neutral", 0),
        "negative": type_counts.get("negative", 0),
    }
    return {
        "total_surveys": len(surveys),
        "total_responses": total_responses,
        "total_respondents": len(respondents),
        "avg_score": round(sum(all_values) / len(all_values), 2) if all_values else None,
        "scale_labels": SURVEY_SCALE_LABELS,
        "scale_distribution": {v: scale_counts.get(v, 0) for v in range(1, SURVEY_SCALE_POINTS + 1)},
        "per_survey": per_survey,
        "response_distribution": response_distribution,
        "summary": _survey_summary_line(response_distribution),
    }


@app.post("/api/pm/surveys/{survey_id}/send")
def pm_send_survey(survey_id: int, claims: dict = Depends(auth.require_pm)):
    """Once sent, the survey shows up in every customer's pending-surveys
    list (list_pending_surveys_for_user) immediately — there's no separate
    targeting step, per the mission's own spec of sending to all users."""
    survey = store.get_custom_survey(survey_id)
    if not survey:
        raise HTTPException(status_code=404, detail="survey not found")
    return store.mark_survey_sent(survey_id)


@app.get("/api/pm/surveys/{survey_id}/results")
def pm_survey_results(survey_id: int, claims: dict = Depends(auth.require_pm)):
    """Per-question answer-count distribution across the scale plus an
    average — pure arithmetic over already-collected responses, same spirit
    as insights.py's aggregation (no LLM involved)."""
    survey = store.get_custom_survey(survey_id)
    if not survey:
        raise HTTPException(status_code=404, detail="survey not found")
    responses = store.list_survey_responses(survey_id)

    questions = []
    all_values = []
    for i, question_text in enumerate(survey["questions"]):
        values = [r["answers"][i] for r in responses if i < len(r["answers"])]
        all_values.extend(values)
        distribution = {v: values.count(v) for v in range(1, SURVEY_SCALE_POINTS + 1)}
        questions.append({
            "question": question_text,
            "distribution": distribution,
            "avg": round(sum(values) / len(values), 2) if values else None,
        })

    type_counts = Counter(_survey_response_type(v) for v in all_values)
    response_distribution = {
        "positive": type_counts.get("positive", 0),
        "neutral": type_counts.get("neutral", 0),
        "negative": type_counts.get("negative", 0),
    }

    return {
        "survey": survey,
        "response_count": len(responses),
        "scale_labels": SURVEY_SCALE_LABELS,
        "questions": questions,
        "response_distribution": response_distribution,
        "avg_score": round(sum(all_values) / len(all_values), 2) if all_values else None,
        "summary": _survey_summary_line(response_distribution),
    }


# ---- customer: answering custom surveys -----------------------------------

@app.get("/api/surveys/pending")
def list_pending_surveys(claims: dict = Depends(auth.require_user)):
    return {"surveys": store.list_pending_surveys_for_user(int(claims["sub"]))}


@app.post("/api/surveys/{survey_id}/answer")
def answer_survey(survey_id: int, req: SurveyAnswerRequest, claims: dict = Depends(auth.require_user)):
    survey = store.get_custom_survey(survey_id)
    if not survey or survey["status"] != "sent":
        raise HTTPException(status_code=404, detail="survey not found or not open")
    if len(req.answers) != len(survey["questions"]):
        raise HTTPException(
            status_code=400, detail=f"expected {len(survey['questions'])} answers, got {len(req.answers)}"
        )
    if any(a < 1 or a > SURVEY_SCALE_POINTS for a in req.answers):
        raise HTTPException(status_code=400, detail=f"each answer must be between 1 and {SURVEY_SCALE_POINTS}")
    response = store.save_survey_response(survey_id, int(claims["sub"]), req.answers)
    return response or {"message": "already answered"}


_frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
