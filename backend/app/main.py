import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from fastapi import Depends, FastAPI, File, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import actions_ai, analytics, auth, classifier, email_service, feedback_ai, insights, narrative_ai, store, ticket_report
from .models import (
    ActionStatusUpdateRequest,
    AdminAssignRequest,
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
    SurveyRequest,
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

app = FastAPI(title="TicketTrident", version="1.0.0")

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
            "Reset your TicketTrident password",
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


def _analyze_and_log_feedback(source_type: str, text: str, source_ref: int | None = None) -> None:
    """Run the PM insights pipeline on one piece of customer voice and log
    it to feedback_items — shared by every ingestion path (ticket creation,
    survey submission, and later review import) so they all feed the same
    unified table the same way."""
    outcome = feedback_ai.analyze_feedback(text)
    a = outcome.analysis
    store.save_feedback_item(
        source_type=source_type,
        source_ref=source_ref,
        text=text,
        sentiment_label=a.sentiment_label.value,
        sentiment_score=a.sentiment_score,
        theme=a.theme,
        urgency_score=a.urgency_score,
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
    (sentiment/theme/urgency) runs independently of routing, on its own
    timeline, without waiting on an Admin to ever pick this ticket up."""
    ticket = store.create_ticket(user_id=int(claims["sub"]), message=req.message)
    _analyze_and_log_feedback("ticket", req.message, source_ref=ticket["id"])
    return ticket


@app.post("/api/surveys")
def submit_survey(req: SurveyRequest, claims: dict = Depends(auth.require_user)):
    """A quick CSAT-style survey response — entirely separate from the
    ticket lifecycle (no team, no status, nothing to route). Always logged
    to feedback_items for the PM dashboard; there is no other consumer of
    this data, so there's nothing to return beyond an acknowledgement."""
    text = f"Survey rating: {req.rating}/5." + (f" Comment: {req.comment}" if req.comment else " No comment provided.")
    _analyze_and_log_feedback("survey", text)
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
        "Your TicketTrident team account",
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
        '```json\n{"category": "Billing", "priority": "High", "team": "Billing Support", '
        '"tone": "angry", "confidence": 0.8, "is_ambiguous": false, "reasoning": "Double charge complaint.",}\n```',
        'Sure! Here is the classification: {"category": "Bug Report", "priority": "Medium", '
        '"team": "Engineering", "tone": "frustrated", "confidence": 0.7, "is_ambiguous": false, '
        '"reasoning": "App crash reported."} Let me know if you need anything else.',
        '{"category": "Security Concern" "priority": "High" "team": "Security Team"}',
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
    """Theme frequency, sentiment distribution, and urgency ranking for one
    period (defaults to the current one). Pass period_key (e.g. "2026-W29")
    to look at a past period — compute_period_insights lists every period
    that actually has data in its own response."""
    if period_type not in insights.PERIOD_TYPES:
        raise HTTPException(status_code=400, detail=f"period_type must be one of {insights.PERIOD_TYPES}")
    return insights.compute_period_insights(period_type, period_key)


@app.get("/api/pm/insights/trend")
def pm_insights_trend(period_type: str = "weekly", period_key: str | None = None, claims: dict = Depends(auth.require_pm)):
    """Period-over-period % change per theme, plus the raw current/previous
    aggregates it was computed from."""
    if period_type not in insights.PERIOD_TYPES:
        raise HTTPException(status_code=400, detail=f"period_type must be one of {insights.PERIOD_TYPES}")
    return insights.compute_trend(period_type, period_key)


@app.post("/api/pm/insights/actions/generate")
def pm_generate_actions(period_type: str = "weekly", period_key: str | None = None, claims: dict = Depends(auth.require_pm)):
    """Recommend actions for whatever themes are worsening or already urgent
    this period, and persist them. Safe to call repeatedly — it always
    appends fresh recommendations rather than overwriting, so re-running
    this after new feedback comes in doesn't erase what a PM already marked
    done on earlier recommendations for the same period."""
    if period_type not in insights.PERIOD_TYPES:
        raise HTTPException(status_code=400, detail=f"period_type must be one of {insights.PERIOD_TYPES}")
    trend = insights.compute_trend(period_type, period_key)
    recommended = actions_ai.recommend_actions(trend)
    saved = [
        store.save_recommended_action(
            period_type=trend["period_type"],
            period_key=trend["current_period_key"],
            theme=a["theme"],
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
        theme_trend=trend["theme_deltas"],
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


@app.get("/api/pm/insights/report")
def pm_get_report(period_type: str = "weekly", period_key: str | None = None, claims: dict = Depends(auth.require_pm)):
    if period_type not in insights.PERIOD_TYPES:
        raise HTTPException(status_code=400, detail=f"period_type must be one of {insights.PERIOD_TYPES}")
    key = period_key or insights.current_period_key(period_type)
    report = store.get_periodic_insight(period_type, key)
    if not report:
        raise HTTPException(status_code=404, detail="no report generated for this period yet")
    return report


_frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
