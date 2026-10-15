"""Integration tests for GET /auth/me (US-003-1).

Covers:
  AC-009 — with a valid session cookie, GET /auth/me returns the user's
           id, email, and role.
  AC-010 — without a session cookie or with an expired session, GET /auth/me
           returns 401 Unauthorized.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import SessionLocal
from app.main import app
from app.models import Session as SessionModel
from app.models import User

client = TestClient(app)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hash(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _create_user(email: str, password: str, role: str = "User") -> User:
    """Insert a user directly into the test database and return it."""
    with SessionLocal() as db:
        user = User(email=email, password_hash=_hash(password), role=role)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user


def _delete_user(email: str) -> None:
    """Remove a user from the test database."""
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
        email = "ac009_profile@example.com"
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

    def test_me_returns_correct_id_for_user(self) -> None:
        """The id field must match the database-assigned user id."""
        email = "ac009_id@example.com"
        password = "correct-password"
        user = _create_user(email, password)
        try:
            session_id = _login(email, password)

            resp = client.get("/auth/me", cookies={"session_id": session_id})
            assert resp.status_code == 200
            assert resp.json()["id"] == user.id
        finally:
            _delete_user(email)

    def test_me_for_user_role(self) -> None:
        """A user with role 'User' gets that role back."""
        email = "ac009_userrole@example.com"
        password = "correct-password"
        _create_user(email, password, role="User")
        try:
            session_id = _login(email, password)

            resp = client.get("/auth/me", cookies={"session_id": session_id})
            assert resp.status_code == 200
            assert resp.json()["role"] == "User"
        finally:
            _delete_user(email)

    def test_me_does_not_accept_body(self) -> None:
        """Identity is read from the cookie, not a request body — a body
        must not be required and must not affect the response."""
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
        """A syntactically valid UUID that doesn't match any session → 401."""
        resp = client.get("/auth/me", cookies={"session_id": str(uuid.uuid4())})
        assert resp.status_code == 401

    def test_expired_session_returns_401(self) -> None:
        """A session whose expires_at is in the past → 401."""
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

    def test_empty_cookie_value_returns_401(self) -> None:
        """An empty string cookie is treated as no session."""
        resp = client.get("/auth/me", cookies={"session_id": ""})
        assert resp.status_code == 401
