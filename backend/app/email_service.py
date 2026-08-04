"""Minimal SMTP email sender, configured entirely via environment variables.

Works with any SMTP provider — a Gmail account + app password, Outlook, or a
real transactional service's SMTP endpoint — no vendor SDK required. If no
SMTP_* vars are set, emails are printed to the server log instead of sent, so
account creation and password resets still work end to end during local dev.
"""
import os
import smtplib
from email.message import EmailMessage

SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
FROM_EMAIL = os.environ.get("FROM_EMAIL") or SMTP_USER or "noreply@nykaapulse.local"


def send_email(to: str, subject: str, body: str) -> bool:
    """Returns True if actually sent over SMTP, False if only logged (no
    SMTP_* configured yet) — callers use this to tell an admin whether they
    still need to relay something manually."""
    if not (SMTP_HOST and SMTP_USER and SMTP_PASSWORD):
        print(f"[email not configured — printing instead]\nTo: {to}\nSubject: {subject}\n\n{body}\n")
        return False

    msg = EmailMessage()
    msg["From"] = FROM_EMAIL
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
    return True
