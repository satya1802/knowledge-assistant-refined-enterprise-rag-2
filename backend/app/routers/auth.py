"""Auth router: login, logout, profile, and password management.

POST /auth/login is implemented with session-cookie management and
failed-login lockout.  Logout, me, and change-password remain stubs
(see US-001-1 task scope).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import LoginAttempt, User
from app.models import Session as SessionModel
from app.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    MessageResponse,
    UserResponse,
)
from app.seed import verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

COOKIE_NAME = "session_id"
COOKIE_MAX_AGE = 86_400  # 24 hours in seconds

LOCKOUT_THRESHOLD = 5
LOCKOUT_WINDOW = timedelta(minutes=15)
LOCKOUT_DURATION = timedelta(minutes=15)

_GENERIC_ERROR = "Invalid email or password"
_LOCKOUT_MESSAGE = (
    "Account temporarily locked due to too many failed login attempts. "
    "Please try again later."
)

# Module-level dependency singleton so ruff's B008 doesn't flag the default.
_db_dependency = Depends(get_db)


def _cookie_secure() -> bool:
    """Secure flag for the session cookie, configurable via COOKIE_SECURE env.

    Defaults to ``False`` for local HTTP development; set ``COOKIE_SECURE=true``
    for HTTPS deployments.
    """
    return os.getenv("COOKIE_SECURE", "false").lower() in ("true", "1", "yes")


# ---------------------------------------------------------------------------
# Lockout helpers
# ---------------------------------------------------------------------------


def _is_locked(email: str, user: User | None, db: Session) -> bool:
    """Return ``True`` when *email* is currently in a lockout period.

    For existing users the persisted ``User.locked_until`` timestamp is the
    primary indicator.  For emails that have no user record (a common
    enumeration-probe scenario) the five most recent failed ``LoginAttempt``
    rows are examined: if they span no more than 15 minutes and the lockout
    window (15 minutes from the most recent of those five) has not elapsed,
    the email is considered locked.
    """
    now = datetime.now(UTC)

    # Existing user — use the persisted timestamp.
    if user is not None and user.locked_until is not None:
        if now < user.locked_until:
            return True
        # Lockout expired — reset and continue.
        user.locked_until = None
        user.failed_login_count = 0
        db.flush()
        return False

    # Non-existent user (or user never locked) — compute from attempt log.
    recent = list(
        db.execute(
            select(LoginAttempt.attempted_at)
            .where(LoginAttempt.email == email, LoginAttempt.success.is_(False))
            .order_by(LoginAttempt.attempted_at.desc())
            .limit(LOCKOUT_THRESHOLD)
        ).scalars()
    )
    if len(recent) >= LOCKOUT_THRESHOLD:
        most_recent = recent[0]
        oldest_of_five = recent[-1]
        if (most_recent - oldest_of_five) <= LOCKOUT_WINDOW:
            lockout_until = most_recent + LOCKOUT_DURATION
            if now < lockout_until:
                return True
    return False


def _count_recent_failures(email: str, db: Session) -> int:
    """Count failed attempts for *email* within the 15-minute lockout window."""
    cutoff = datetime.now(UTC) - LOCKOUT_WINDOW
    rows = db.execute(
        select(LoginAttempt.id)
        .where(
            LoginAttempt.email == email,
            LoginAttempt.success.is_(False),
            LoginAttempt.attempted_at >= cutoff,
        )
    ).all()
    return len(rows)


def _record_attempt(email: str, success: bool, db: Session) -> None:
    """Persist a login-attempt audit row."""
    db.add(LoginAttempt(email=email, success=success))
    db.flush()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/login", response_model=UserResponse)
async def login(
    request: LoginRequest,
    response: Response,
    db: Session = _db_dependency,
) -> UserResponse:
    """Authenticate a user and set an HTTP-only session cookie.

    On success returns the user profile ``{id, email, role}`` and sets a
    ``session_id`` cookie.  On failure returns a generic error so a wrong
    email cannot be distinguished from a wrong password.  After 5 failures
    within 15 minutes the email is locked for 15 minutes and a distinct
    lockout message is returned.
    """
    email = request.email
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()

    # --- Lockout check (before credential verification) ---
    if _is_locked(email, user, db):
        raise HTTPException(status_code=423, detail=_LOCKOUT_MESSAGE)

    # --- Credential verification ---
    try:
        password_ok = user is not None and verify_password(
            request.password, user.password_hash
        )
    except (ValueError, TypeError):
        # Corrupted or malformed hash — treat as a failed login.
        password_ok = False

    if not password_ok:
        _record_attempt(email, False, db)
        if user is not None:
            recent_failures = _count_recent_failures(email, db)
            user.failed_login_count = recent_failures
            if recent_failures >= LOCKOUT_THRESHOLD:
                user.locked_until = datetime.now(UTC) + LOCKOUT_DURATION
        db.commit()
        raise HTTPException(status_code=401, detail=_GENERIC_ERROR)

    # --- Success ---
    assert user is not None  # password_ok guarantees user exists

    _record_attempt(email, True, db)
    user.failed_login_count = 0
    user.locked_until = None

    session = SessionModel(
        user_id=user.id,
        expires_at=datetime.now(UTC) + timedelta(seconds=COOKIE_MAX_AGE),
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    response.set_cookie(
        key=COOKIE_NAME,
        value=str(session.id),
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
        path="/",
    )

    return UserResponse(id=user.id, email=user.email, role=user.role)


# ---------------------------------------------------------------------------
# Stubs — not implemented in this task (see task constraints).
# ---------------------------------------------------------------------------


@router.post("/logout", response_model=MessageResponse)
async def logout() -> None:
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/me", response_model=UserResponse)
async def me() -> None:
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/change-password", response_model=MessageResponse)
async def change_password(request: ChangePasswordRequest) -> None:
    raise HTTPException(status_code=501, detail="Not implemented")