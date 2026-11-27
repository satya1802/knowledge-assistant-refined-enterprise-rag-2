"""Unit tests for POST /conversations (US-026).

Covers:
  AC-074 — an authenticated user calling POST /conversations gets a new
           conversation record created in the database, associated with
           their own user ID, and its details returned in the response.

Follows the patterns established in test_users.py: TestClient, direct DB
inserts for fixtures, login to obtain session cookies, try/finally cleanup.
"""

from __future__ import annotations

import bcrypt
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import SessionLocal
from app.main import app
from app.models import Conversation, User

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hash(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _create_user(email: str, password: str, role: str = "Regular User") -> User:
    """Insert a user directly into the test database and return it."""
    with SessionLocal() as db:
        user = User(email=email, password_hash=_hash(password), role=role)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user


def _delete_user(email: str) -> None:
    """Remove a user (and its conversations, via cascade) from the test database."""
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


def _conversations_for_user(user_id: int) -> list[Conversation]:
    with SessionLocal() as db:
        return list(
            db.execute(select(Conversation).where(Conversation.user_id == user_id)).scalars()
        )


# ---------------------------------------------------------------------------
# AC-074 — create conversation for the authenticated user
# ---------------------------------------------------------------------------


class TestAc074CreateConversation:
    def test_ac074_creates_conversation_record_associated_with_user(self) -> None:
        email = "us026_create_conv@example.com"
        password = "conv-password-123"
        user = _create_user(email, password)
        try:
            session_id = _login(email, password)

            resp = client.post(
                "/conversations",
                json={"title": "My first question"},
                cookies={"session_id": session_id},
            )

            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert "id" in body
            assert body["title"] == "My first question"
            assert "created_at" in body

            rows = _conversations_for_user(user.id)
            assert len(rows) == 1
            assert str(rows[0].id) == body["id"]
            assert rows[0].user_id == user.id
            assert rows[0].title == "My first question"
        finally:
            _delete_user(email)

    def test_ac074_title_is_optional(self) -> None:
        email = "us026_no_title@example.com"
        password = "conv-password-123"
        user = _create_user(email, password)
        try:
            session_id = _login(email, password)

            resp = client.post(
                "/conversations",
                json={},
                cookies={"session_id": session_id},
            )

            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["title"] is None

            rows = _conversations_for_user(user.id)
            assert len(rows) == 1
            assert rows[0].title is None
        finally:
            _delete_user(email)

    def test_ac074_blank_title_is_stored_as_none(self) -> None:
        email = "us026_blank_title@example.com"
        password = "conv-password-123"
        user = _create_user(email, password)
        try:
            session_id = _login(email, password)

            resp = client.post(
                "/conversations",
                json={"title": "   "},
                cookies={"session_id": session_id},
            )

            assert resp.status_code == 200, resp.text
            assert resp.json()["title"] is None

            rows = _conversations_for_user(user.id)
            assert rows[0].title is None
        finally:
            _delete_user(email)

    def test_ac074_conversation_associated_with_calling_user_not_another(self) -> None:
        email_a = "us026_user_a@example.com"
        email_b = "us026_user_b@example.com"
        password = "conv-password-123"
        user_a = _create_user(email_a, password)
        user_b = _create_user(email_b, password)
        try:
            session_a = _login(email_a, password)

            resp = client.post(
                "/conversations",
                json={"title": "Belongs to A"},
                cookies={"session_id": session_a},
            )

            assert resp.status_code == 200, resp.text

            assert len(_conversations_for_user(user_a.id)) == 1
            assert len(_conversations_for_user(user_b.id)) == 0
        finally:
            _delete_user(email_a)
            _delete_user(email_b)

    def test_ac074_unauthenticated_request_rejected(self) -> None:
        resp = client.post("/conversations", json={"title": "No session"})

        assert resp.status_code == 401

    def test_ac074_each_call_creates_a_distinct_conversation(self) -> None:
        email = "us026_multiple_conv@example.com"
        password = "conv-password-123"
        user = _create_user(email, password)
        try:
            session_id = _login(email, password)

            first = client.post(
                "/conversations",
                json={"title": "First"},
                cookies={"session_id": session_id},
            )
            second = client.post(
                "/conversations",
                json={"title": "Second"},
                cookies={"session_id": session_id},
            )

            assert first.status_code == 200, first.text
            assert second.status_code == 200, second.text
            assert first.json()["id"] != second.json()["id"]

            rows = _conversations_for_user(user.id)
            assert len(rows) == 2
        finally:
            _delete_user(email)
