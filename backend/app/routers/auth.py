"""Auth router: login, logout, profile, and password management.

POST /auth/login is implemented with session-cookie management and
failed-login lockout.  Logout and me are implemented here; change-password
is implemented here too.

``get_current_user`` is the reusable session-validation dependency that
every protected endpoint across the application should use: it reads the
``session_id`` cookie, converts it to a ``uuid.UUID``, looks up the
``Session`` row, verifies it has not expired, and returns the associated
``User`` -- or raises ``401`` when any of those steps fail.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import bcrypt
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
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
    "Account temporarily locked due to too many failed login attempts. Please try again later."
)
_UNAUTHORIZED = "Not authenticated"
_WRONG_CURRENT_PASSWORD = "Current password is incorrect"

# Module-level dependency singleton for the DB session so ruff's B008 doesn't
# flag the default.
_db_dependency = Depends(get_db)


def _cookie_secure() -> bool:
    """Secure flag for the session cookie, configurable via COOKIE_SECURE env.

    Defaults to ``False`` for local HTTP development; set ``COOKIE_SECURE=true``
    for HTTPS deployments.
    """
    return os.getenv("COOKIE_SECURE", "false").lower() in ("true", "1", "yes")


def _hash_password(plaintext: str) -> str:
    """Return a bcrypt hash of *plaintext*."""
    return bcrypt.hashpw(plaintext.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


# ---------------------------------------------------------------------------
# Session-validation dependency
# ---------------------------------------------------------------------------


def get_current_user(
    session_id: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: Session = _db_dependency,
) -> User:
    """Validate the session cookie and return the authenticated ``User``.

    Reads the ``session_id`` cookie, converts it to a ``uuid.UUID`` via
    :func:`SessionModel.lookup_id`, looks up the ``Session`` row, and verifies
    it has not expired.  On any failure (missing cookie, malformed UUID, no
    matching session, expired session) raises ``401 Unauthorized``.

    All protected endpoints should depend on this to obtain the current user.
    """
    if not session_id:
        raise HTTPException(status_code=401, detail=_UNAUTHORIZED)

    try:
        parsed_id = SessionModel.lookup_id(session_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail=_UNAUTHORIZED) from None

    session = db.execute(
        select(SessionModel).where(SessionModel.id == parsed_id)
    ).scalar_one_or_none()

    if session is None:
        raise HTTPException(status_code=401, detail=_UNAUTHORIZED)

    if session.expires_at <= datetime.now(UTC):
        raise HTTPException(status_code=401, detail=_UNAUTHORIZED)

    user = session.user
    if user is None:
        raise HTTPException(status_code=401, detail=_UNAUTHORIZED)

    return user


# Module-level singleton for the current-user dependency (defined after
# get_current_user so the name is available).
_current_user_dependency = Depends(get_current_user)


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
        select(LoginAttempt.id).where(
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
        password_ok = user is not None and verify_password(request.password, user.password_hash)
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


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    response: Response,
    current_user: User = _current_user_dependency,
    db: Session = _db_dependency,
) -> MessageResponse:
    """Invalidate the current session server-side and clear the session cookie.

    Requires a valid session cookie (via :func:`get_current_user`).  Deletes
    the ``Session`` row from the database so the old cookie cannot be reused,
    then clears the cookie from the browser.  Returns a success message.
    """
    session_id = request.cookies.get(COOKIE_NAME)
    if session_id:
        try:
            parsed_id = SessionModel.lookup_id(session_id)
            session = db.execute(
                select(SessionModel).where(SessionModel.id == parsed_id)
            ).scalar_one_or_none()
            if session is not None:
                db.delete(session)
                db.commit()
        except (ValueError, TypeError):
            pass

    response.delete_cookie(key=COOKIE_NAME, path="/")
    return MessageResponse(message="Logged out successfully")


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = _current_user_dependency) -> UserResponse:
    """Return the authenticated user's ``{id, email, role}``.

    Requires a valid session cookie (via :func:`get_current_user`).  Reads
    identity purely from the cookie — no request body is accepted.  Returns
    ``401 Unauthorized`` when no session cookie is present or the session is
    expired or invalid.
    """
    return UserResponse(id=current_user.id, email=current_user.email, role=current_user.role)


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = _current_user_dependency,
    db: Session = _db_dependency,
) -> MessageResponse:
    """Change the authenticated user's password.

    Requires a valid session cookie (via :func:`get_current_user`).  Verifies
    the supplied current password against the stored hash; if it does not
    match, returns ``400`` with a message indicating the current password is
    incorrect.  On success, replaces the stored hash with a bcrypt hash of
    the new password and returns a success message.
    """
    try:
        current_ok = verify_password(request.current_password, current_user.password_hash)
    except (ValueError, TypeError):
        current_ok = False

    if not current_ok:
        raise HTTPException(status_code=400, detail=_WRONG_CURRENT_PASSWORD)

    current_user.password_hash = _hash_password(request.new_password)
    db.commit()

    return MessageResponse(message="Password changed successfully")
