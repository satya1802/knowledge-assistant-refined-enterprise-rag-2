"""Integration tests for POST /auth/logout (US-003-1).

Covers:
  AC-007 — logout invalidates the session server-side and clears the session
           cookie (Set-Cookie header expires/deletes the cookie).
  AC-008 — after logout, a subsequent request using the old session cookie
           is rejected as unauthenticated (401 or equivalent).
"""

from __future__ import annotations

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
# AC-007 — logout invalidates session server-side and clears cookie
# ---------------------------------------------------------------------------


class TestLogoutClearsSession:
    def test_logout_returns_success(self) -> None:
        email = "ac007_success@example.com"
        password = "correct-password"
        _create_user(email, password)
        try:
            session_id = _login(email, password)
            resp = client.post("/auth/logout", cookies={"session_id": session_id})
            assert resp.status_code in (200, 204)
            if resp.status_code == 200:
                assert "message" in resp.json()
        finally:
            _delete_user(email)

    def test_logout_clears_cookie_via_set_cookie_header(self) -> None:
        """The Set-Cookie header on the logout response must expire/delete
        the session cookie (max-age=0 or an expiry in the past)."""
        email = "ac007_clear@example.com"
        password = "correct-password"
        _create_user(email, password)
        try:
            session_id = _login(email, password)
            resp = client.post("/auth/logout", cookies={"session_id": session_id})
            assert resp.status_code in (200, 204)

            set_cookie = resp.headers.get("set-cookie", "")
            assert "session_id=" in set_cookie
            # The cookie is deleted by setting max-age=0 or an expiry in the
            # past.  Either form is acceptable.
            lowered = set_cookie.lower()
            assert "max-age=0" in lowered or "expires=" in lowered
        finally:
            _delete_user(email)

    def test_logout_deletes_session_record_server_side(self) -> None:
        """The Session row must be removed from the database after logout."""
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
        """Logout requires authentication — no cookie means 401."""
        resp = client.post("/auth/logout")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# AC-008 — after logout, old session cookie is rejected
# ---------------------------------------------------------------------------


class TestLogoutInvalidatesOldCookie:
    def test_old_cookie_rejected_on_me_after_logout(self) -> None:
        """After logout, GET /auth/me with the old cookie returns 401."""
        email = "ac008_me@example.com"
        password = "correct-password"
        _create_user(email, password)
        try:
            session_id = _login(email, password)

            # Confirm the cookie works before logout.
            resp = client.get("/auth/me", cookies={"session_id": session_id})
            assert resp.status_code == 200

            # Logout.
            client.post("/auth/logout", cookies={"session_id": session_id})

            # Old cookie must now be rejected.
            resp = client.get("/auth/me", cookies={"session_id": session_id})
            assert resp.status_code == 401
        finally:
            _delete_user(email)

    def test_old_cookie_rejected_on_logout_after_logout(self) -> None:
        """After logout, POST /auth/logout again with the old cookie returns 401."""
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

    def test_other_sessions_remain_valid_after_logout(self) -> None:
        """Logging out one session must not invalidate a different session
        for the same user (exploratory: session-scoped invalidation)."""
        email = "ac008_othersession@example.com"
        password = "correct-password"
        _create_user(email, password)
        try:
            # Two independent logins → two sessions.
            sid_a = _login(email, password)
            sid_b = _login(email, password)
            assert sid_a != sid_b

            # Logout session A.
            client.post("/auth/logout", cookies={"session_id": sid_a})

            # Session A is now invalid.
            resp_a = client.get("/auth/me", cookies={"session_id": sid_a})
            assert resp_a.status_code == 401

            # Session B must still work.
            resp_b = client.get("/auth/me", cookies={"session_id": sid_b})
            assert resp_b.status_code == 200

            # Clean up session B.
            client.post("/auth/logout", cookies={"session_id": sid_b})
        finally:
            _delete_user(email)