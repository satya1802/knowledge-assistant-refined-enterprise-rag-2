"""Idempotent admin account seeding at application startup.

Seeding runs after ``Base.metadata.create_all`` in ``main.py``. On first
startup it creates the admin user ``satya.ganaraju@quorq.ai`` with role
``Administrator`` and a bcrypt hash of ``admin@123``. On subsequent startups
the existing admin is left untouched -- no password reset, no duplicate.

The plaintext password is never stored in the database or written to
application logs; only the bcrypt hash persists.
"""

from __future__ import annotations

import logging

import bcrypt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User

logger = logging.getLogger(__name__)

ADMIN_EMAIL = "satya.ganaraju@quorq.ai"
ADMIN_ROLE = "Administrator"
ADMIN_PASSWORD = "admin@123"


def _hash_password(plaintext: str) -> str:
    """Return a bcrypt hash of *plaintext*.

    The plaintext is consumed in-memory and never persisted or logged.
    """
    return bcrypt.hashpw(plaintext.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plaintext: str, password_hash: str) -> bool:
    """Check *plaintext* against a stored bcrypt *password_hash*."""
    return bcrypt.checkpw(plaintext.encode("utf-8"), password_hash.encode("utf-8"))


def seed_admin(session: Session) -> None:
    """Create the admin user if it does not already exist.

    Idempotent: when the admin already exists (even with a changed password),
    the record is left unchanged. No password reset, no duplicate.
    """
    existing = session.execute(select(User).where(User.email == ADMIN_EMAIL)).scalar_one_or_none()

    if existing is not None:
        # Leave the existing record untouched -- no reset, no duplicate.
        logger.debug("Admin user %s already exists; skipping seed.", ADMIN_EMAIL)
        return

    user = User(
        email=ADMIN_EMAIL,
        password_hash=_hash_password(ADMIN_PASSWORD),
        role=ADMIN_ROLE,
    )
    session.add(user)
    session.commit()
    logger.info("Seeded admin user %s.", ADMIN_EMAIL)
