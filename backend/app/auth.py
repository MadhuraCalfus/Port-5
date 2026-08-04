"""Password hashing, JWT issuing/verification, and role-gated FastAPI
dependencies for the four account types: user, team member, admin, PM.

There's no separate admin table (see the plan) — a single admin account is
configured via ADMIN_EMAIL/ADMIN_PASSWORD in .env and checked directly,
since it's not multi-account like users/team_members and never touches the
database (so a DB leak can't expose it). PM is the same shape as admin — a
single fixed account via PM_EMAIL/PM_PASSWORD — and deliberately not a role
Admin can create or manage; all three are peers.
"""
import os
import secrets
import time

import bcrypt
import jwt
from fastapi import HTTPException, Request

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRES_SECONDS = 60 * 60 * 24 * 7  # 7 days

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@nykaapulse.local")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")

PM_EMAIL = os.environ.get("PM_EMAIL", "pm@nykaapulse.local")
PM_PASSWORD = os.environ.get("PM_PASSWORD", "pm")


def generate_reset_token() -> str:
    return secrets.token_urlsafe(32)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_token(subject: int | str, role: str, name: str, team: str | None = None) -> str:
    # JWT's "sub" claim is conventionally a string (RFC 7519) even when the
    # underlying id is a DB integer — callers cast back with int(claims["sub"])
    # wherever it's used to look up a user/team-member row.
    payload = {
        "sub": str(subject),
        "role": role,
        "name": name,
        "team": team,
        "exp": int(time.time()) + JWT_EXPIRES_SECONDS,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _decode_claims(request: Request) -> dict:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = auth_header.removeprefix("Bearer ")
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="invalid or expired token")


def require_any(request: Request) -> dict:
    """Any logged-in account, regardless of role — used by /api/auth/me."""
    return _decode_claims(request)


def require_user(request: Request) -> dict:
    claims = _decode_claims(request)
    if claims["role"] != "user":
        raise HTTPException(status_code=403, detail="a user account is required for this action")
    return claims


def require_user_optional(request: Request) -> dict | None:
    """Same as require_user, but returns None instead of raising when there's
    no bearer token at all — for the handful of endpoints a logged-out
    visitor can also use (e.g. app feedback submitted from the login page),
    which still attribute the submission to a real account whenever one is
    logged in. A present-but-invalid/wrong-role token still raises, same as
    require_user — this only relaxes the "no token at all" case."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    return require_user(request)


def require_team(request: Request) -> dict:
    claims = _decode_claims(request)
    if claims["role"] != "team":
        raise HTTPException(status_code=403, detail="a team-member account is required for this action")
    return claims


def require_admin(request: Request) -> dict:
    claims = _decode_claims(request)
    if claims["role"] != "admin":
        raise HTTPException(status_code=403, detail="an admin account is required for this action")
    return claims


def require_pm(request: Request) -> dict:
    claims = _decode_claims(request)
    if claims["role"] != "pm":
        raise HTTPException(status_code=403, detail="a product manager account is required for this action")
    return claims
