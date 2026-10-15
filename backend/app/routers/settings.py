"""Settings router: view and update application settings (admin only).

Both endpoints require a valid session cookie (``get_current_user`` raises
``401`` when one is absent) and restrict access to users whose ``role`` is
``"Administrator"`` -- any other authenticated user receives ``403``.

``GET /settings`` returns the singleton ``Settings`` row (the four live
configuration values the rest of the application reads at runtime).

``PATCH /settings`` applies partial-update semantics: only fields whose value
is non-null in ``SettingsUpdateRequest`` are written to the database.  The
updated row is persisted and returned, so the response always reflects the
new state of the singleton.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Settings, User
from app.routers.auth import get_current_user
from app.schemas import SettingsResponse, SettingsUpdateRequest
from app.services import get_current_settings

router = APIRouter(prefix="/settings", tags=["settings"])

# Module-level dependency singletons so ruff's B008 doesn't flag defaults.
_db_dependency = Depends(get_db)
_current_user_dependency = Depends(get_current_user)


def _require_admin(current_user: User) -> None:
    """Raise ``403`` unless *current_user* is an Administrator."""
    if current_user.role != "Administrator":
        raise HTTPException(status_code=403, detail="Administrator access required")


def _to_response(settings: Settings) -> SettingsResponse:
    """Convert a ``Settings`` ORM row into a ``SettingsResponse``."""
    return SettingsResponse(
        gemini_answer_model=settings.gemini_answer_model,
        gemini_embedding_model=settings.gemini_embedding_model,
        cosine_threshold=settings.cosine_threshold,
        cookie_secure_flag=settings.cookie_secure_flag,
    )


@router.get("", response_model=SettingsResponse)
async def get_settings(
    db: Session = _db_dependency,
    current_user: User = _current_user_dependency,
) -> SettingsResponse:
    """Return the current application settings (admin only)."""
    _require_admin(current_user)
    settings = get_current_settings(db)
    return _to_response(settings)


@router.patch("", response_model=SettingsResponse)
async def update_settings(
    request: SettingsUpdateRequest,
    db: Session = _db_dependency,
    current_user: User = _current_user_dependency,
) -> SettingsResponse:
    """Update application settings with partial-update semantics (admin only).

    Only fields that are non-null in *request* are written to the database.
    """
    _require_admin(current_user)
    settings = get_current_settings(db)

    if request.gemini_answer_model is not None:
        settings.gemini_answer_model = request.gemini_answer_model
    if request.gemini_embedding_model is not None:
        settings.gemini_embedding_model = request.gemini_embedding_model
    if request.cosine_threshold is not None:
        settings.cosine_threshold = request.cosine_threshold
    if request.cookie_secure_flag is not None:
        settings.cookie_secure_flag = request.cookie_secure_flag

    db.commit()
    db.refresh(settings)

    return _to_response(settings)
