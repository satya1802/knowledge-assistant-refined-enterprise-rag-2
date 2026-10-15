"""Users router: list and create user accounts (admin only).

Both endpoints require a valid session cookie (``get_current_user`` raises
``401`` when one is absent) and restrict access to users whose ``role`` is
``"Administrator"`` -- any other authenticated user receives ``403``.

``POST /users`` validates the supplied ``role`` against the two accepted
values (``"Administrator"`` and ``"Regular User"``), hashes the password with
bcrypt before storage, and rejects a duplicate email with ``409``.  No public
self-registration endpoint exists here or anywhere in the application.
"""

from __future__ import annotations

import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.routers.auth import get_current_user
from app.schemas import CreateUserRequest, UserResponse

router = APIRouter(prefix="/users", tags=["users"])

# Module-level dependency singletons so ruff's B008 doesn't flag defaults.
_db_dependency = Depends(get_db)
_current_user_dependency = Depends(get_current_user)

# Roles accepted by POST /users.  The ``User.role`` column stores these
# verbatim; anything else is rejected with 422.
_VALID_ROLES = frozenset({"Administrator", "Regular User"})


def _hash_password(plaintext: str) -> str:
    """Return a bcrypt hash of *plaintext* (mirrors app.seed._hash_password)."""
    return bcrypt.hashpw(plaintext.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _require_admin(current_user: User) -> None:
    """Raise ``403`` unless *current_user* is an Administrator."""
    if current_user.role != "Administrator":
        raise HTTPException(status_code=403, detail="Administrator access required")


@router.get("", response_model=list[UserResponse])
async def list_users(
    db: Session = _db_dependency,
    current_user: User = _current_user_dependency,
) -> list[UserResponse]:
    """Return every user as ``{id, email, role}`` (admin only).

    Password hashes are never included in the response.
    """
    _require_admin(current_user)
    users = db.execute(select(User).order_by(User.id)).scalars().all()
    return [UserResponse(id=u.id, email=u.email, role=u.role) for u in users]


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    request: CreateUserRequest,
    db: Session = _db_dependency,
    current_user: User = _current_user_dependency,
) -> UserResponse:
    """Create a new user account (admin only).

    Validates the role, hashes the password with bcrypt, enforces email
    uniqueness (``409`` on conflict), and returns the new user profile.
    """
    _require_admin(current_user)

    # --- Role validation (422 for anything outside the allowed set) ---
    if request.role not in _VALID_ROLES:
        raise HTTPException(
            status_code=422,
            detail="Invalid role; must be 'Administrator' or 'Regular User'",
        )

    # --- Email uniqueness (409 on duplicate) ---
    existing = (
        db.execute(select(User).where(User.email == request.email))
        .scalar_one_or_none()
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Email already registered")

    # --- Create the user with a bcrypt-hashed password ---
    user = User(
        email=request.email,
        password_hash=_hash_password(request.password),
        role=request.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return UserResponse(id=user.id, email=user.email, role=user.role)