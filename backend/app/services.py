"""The backing services this application is configured to reach.

Each entry maps a service to the environment variable that addresses it. The value
comes from docker-compose.yml through .env.example, so the health check reports
what the running deployment can actually reach.

:func:`get_current_settings` is the runtime accessor that chat, embedding, and
RAG code call to read the live configuration values (cosine threshold, Gemini
model names, cookie-secure flag) from the database at query time.
"""

from __future__ import annotations

import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Settings

SERVICES = {
    "redis-queue": "REDIS_URL",
    "gemini-api": "GEMINI_API_KEY",
}


def configured_services() -> dict[str, bool]:
    """Each service mapped to whether its connection variable is set."""
    return {name: bool(os.getenv(var)) for name, var in SERVICES.items()}


def get_current_settings(db: Session) -> Settings:
    """Return the singleton ``Settings`` row, creating it with defaults if absent.

    Future chat, embedding, and RAG code should call this function at query
    time (not cache the result) so that updates made via ``PATCH /settings``
    take effect immediately without a restart.

    The singleton row is always ``id=1``.  If it does not yet exist -- e.g.
    on a fresh database -- it is inserted with the default values declared on
    the ``Settings`` model, committed, and returned.
    """
    settings = db.execute(select(Settings).where(Settings.id == 1)).scalar_one_or_none()

    if settings is None:
        settings = Settings(id=1)
        db.add(settings)
        db.commit()
        db.refresh(settings)

    return settings