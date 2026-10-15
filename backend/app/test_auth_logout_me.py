"""Integration tests for POST /auth/logout and GET /auth/me (US-003-1).

These tests live inside ``backend/app/`` because the task scope restricts
writes to ``backend/app/`` and ``backend/app/routers/``.  They replicate the
test-database bootstrap that ``backend/tests/conftest.py`` performs so they
can run standalone with ``pytest backend/app/test_auth_logout_me.py``.

Covers:
  AC-007 — logout invalidates the session server-side and clears the cookie.
  AC-008 — after logout, the old session cookie is rejected (401).
  AC-009 — a valid session cookie returns {id, email, role} from GET /auth/me.
  AC-010 — no cookie or an expired session yields 401 from GET /auth/me.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Point at a throwaway database and remove any pre-existing files BEFORE
# importing the application (which creates tables at import time).
os.environ["DATABASE_URL"] = "sqlite:///./test_logout_me.db"
for _name in ("app.db", "test_logout_me.db"):
    _p = Path(_name)
    if _p.exists():
        _p.unlink()

import bcrypt  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Session as SessionModel  # noqa: E402
from app.models import User  # noqa: E402

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hash(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _create_user(email: str, password: str, role: str = "User") -> User:
    with SessionLocal() as db:
        user = User(email=email, password_hash=_hash(password), role=role)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user


def _delete_user(email: str) -> None:
    with SessionLocal() as db:
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is not None:
            db.delete(user)
        db.commit()


def _login(email: str, password: str) -> str:
    """Log in and return the session_id cookie value."""
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.cookies.get("session_id") or ""


# ---------------------------------------------------------------------------
# AC-009 — valid session cookie returns {id, email, role}
# ---------------------------------------------------------------------------


class TestGetMe:
    def test_valid_session_returns_user_profile(self) -> None:
        email = "ac009_me@example.com"
        password = "correct-password"
        user = _create_user(email, password, role="Administrator")
        try:
            session_id = _login(email, password)
            assert session_id

            resp = client.get("/auth/me", cookies={"session_id": session_id})

            assert resp.status_code == 200
            body = resp.json()
            assert set(body.keys()) == {"id", "email", "role"}
            assert body["id"] == user.id
            assert body["email"] == email
            assert body["role"] == "Administrator"
        finally:
            _delete_user(email)

    def test_me_does_not_require_body(self) -> None:
        email = "ac009_nobody@example.com"
        password = "correct-password"
        _create_user(email, password)
        try:
            session_id = _login(email, password)

            resp = client.get("/auth/me", cookies={"session_id": session_id})

            assert resp.status_code == 200
        finally:
            _delete_user(email)


# ---------------------------------------------------------------------------
# AC-010 — no cookie or expired session → 401
# ---------------------------------------------------------------------------


class TestGetMeUnauthorized:
    def test_no_cookie_returns_401(self) -> None:
        resp = client.get("/auth/me")
        assert resp.status_code == 401

    def test_invalid_uuid_cookie_returns_401(self) -> None:
        resp = client.get("/auth/me", cookies={"session_id": "not-a-uuid"})
        assert resp.status_code == 401

    def test_nonexistent_session_returns_401(self) -> None:
        import uuid

        resp = client.get("/auth/me", cookies={"session_id": str(uuid.uuid4())})
        assert resp.status_code == 401

    def test_expired_session_returns_401(self) -> None:
        email = "ac010_expired@example.com"
        password = "correct-password"
        _create_user(email, password)
        try:
            session_id = _login(email, password)

            with SessionLocal() as db:
                session = db.execute(
                    select(SessionModel).where(
                        SessionModel.id == SessionModel.lookup_id(session_id)
                    )
                ).scalar_one()
                session.expires_at = datetime.now(UTC) - timedelta(minutes=5)
                db.commit()

            resp = client.get("/auth/me", cookies={"session_id": session_id})
            assert resp.status_code == 401
        finally:
            _delete_user(email)


# ---------------------------------------------------------------------------
# AC-007 — logout invalidates session and clears cookie
# ---------------------------------------------------------------------------


class TestLogout:
    def test_logout_returns_success(self) -> None:
        email = "ac007_logout@example.com"
        password = "correct-password"
        _create_user(email, password)
        try:
            session_id = _login(email, password)
            resp = client.post("/auth/logout", cookies={"session_id": session_id})
            assert resp.status_code in (200, 204)
        finally:
            _delete_user(email)

    def test_logout_clears_cookie(self) -> None:
        email = "ac007_clear@example.com"
        password = "correct-password"
        _create_user(email, password)
        try:
            session_id = _login(email, password)
            resp = client.post("/auth/logout", cookies={"session_id": session_id})
            assert resp.status_code in (200, 204)

            set_cookie = resp.headers.get("set-cookie", "")
            assert "session_id=" in set_cookie
            assert "max-age=0" in set_cookie.lower() or "expires=" in set_cookie.lower()
        finally:
            _delete_user(email)

    def test_logout_deletes_session_record(self) -> None:
        email = "ac007_delete@example.com"
        password = "correct-password"
        _create_user(email, password)
        try:
            session_id = _login(email, password)

            with SessionLocal() as db:
                session = db.execute(
                    select(SessionModel).where(
                        SessionModel.id == SessionModel.lookup_id(session_id)
                    )
                ).scalar_one_or_none()
                assert session is not None

            client.post("/auth/logout", cookies={"session_id": session_id})

            with SessionLocal() as db:
                session = db.execute(
                    select(SessionModel).where(
                        SessionModel.id == SessionModel.lookup_id(session_id)
                    )
                ).scalar_one_or_none()
                assert session is None
        finally:
            _delete_user(email)

    def test_logout_without_cookie_returns_401(self) -> None:
        resp = client.post("/auth/logout")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# AC-008 — after logout, old cookie is rejected
# ---------------------------------------------------------------------------


class TestLogoutInvalidatesSession:
    def test_old_cookie_rejected_after_logout_on_me(self) -> None:
        email = "ac008_me@example.com"
        password = "correct-password"
        _create_user(email, password)
        try:
            session_id = _login(email, password)

            resp = client.get("/auth/me", cookies={"session_id": session_id})
            assert resp.status_code == 200

            client.post("/auth/logout", cookies={"session_id": session_id})

            resp = client.get("/auth/me", cookies={"session_id": session_id})
            assert resp.status_code == 401
        finally:
            _delete_user(email)

    def test_old_cookie_rejected_after_logout_on_logout(self) -> None:
        email = "ac008_logout@example.com"
        password = "correct-password"
        _create_user(email, password)
        try:
            session_id = _login(email, password)

            client.post("/auth/logout", cookies={"session_id": session_id})

            resp = client.post("/auth/logout", cookies={"session_id": session_id})
            assert resp.status_code == 401
        finally:
            _delete_user(email)
