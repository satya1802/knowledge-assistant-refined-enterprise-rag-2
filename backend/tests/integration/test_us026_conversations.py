"""Integration tests for POST /conversations — create a new chat conversation
for the authenticated user (US-026).

Covers:
  AC-074 — an authenticated user calls POST /conversations: a new conversation
           record is created in the database associated with the user's ID
           and the conversation details are returned.

Field-name note: this task does not include the OpenAPI spec. The response
is expected to carry an ``id`` and a ``created_at`` timestamp, following the
snake_case field-naming convention already used elsewhere in this test kit
(e.g. ``created_at`` for documents in test_documents.py, and
``document_id``/``chunk_id`` for citations in test_us023_rag_chat.py). See
the task report's ``risk`` field.

Follows patterns from test_us023_rag_chat.py and test_documents.py:
TestClient, direct DB inserts for fixtures, login to obtain session cookies,
try/finally cleanup.
"""

from __future__ import annotations

import bcrypt
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Conversation, Message, User

# Ensure all tables exist on the test database (conftest.py sets DATABASE_URL
# and removes stale DB files before this module is imported).
Base.metadata.create_all(bind=engine)

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hash(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _create_user(email: str, role: str = "Regular User") -> tuple[User, str]:
    """Insert a user directly into the test database; return (user, password)."""
    password = secrets_token()
    with SessionLocal() as db:
        user = User(email=email, password_hash=_hash(password), role=role)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user, password


def secrets_token() -> str:
    import secrets

    return secrets.token_urlsafe(16)


def _delete_user(email: str) -> None:
    with SessionLocal() as db:
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is not None:
            db.delete(user)
        db.commit()


def _login(email: str, password: str) -> str:
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.cookies.get("session_id") or ""


def _logout(session_id: str) -> None:
    client.post("/auth/logout", cookies={"session_id": session_id})


def _cleanup_conversations() -> None:
    """Remove messages and conversations so one test cannot see another's data."""
    with SessionLocal() as db:
        for message in db.execute(select(Message)).scalars().all():
            db.delete(message)
        for conversation in db.execute(select(Conversation)).scalars().all():
            db.delete(conversation)
        db.commit()


def _conversation_count() -> int:
    with SessionLocal() as db:
        return len(db.execute(select(Conversation)).scalars().all())


def _get_conversation(conversation_id: int) -> Conversation:
    with SessionLocal() as db:
        return db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        ).scalar_one()


# ---------------------------------------------------------------------------
# TC-001 (AC-074) — create conversation for authenticated user
# ---------------------------------------------------------------------------


def test_tc001_create_conversation_for_authenticated_user() -> None:
    email = "us026_tc001_alice@example.com"
    user, password = _create_user(email, role="Regular User")
    session_id = ""
    try:
        _cleanup_conversations()
        session_id = _login(email, password)

        resp = client.post(
            "/conversations",
            cookies={"session_id": session_id},
        )

        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert "id" in body, f"response missing conversation id: {body}"
        assert body["id"] is not None
        assert "created_at" in body, f"response missing creation timestamp: {body}"
        assert body["created_at"]

        # Post-condition: the record exists in the DB, linked to alice's user ID.
        conversation = _get_conversation(body["id"])
        assert conversation.user_id == user.id
    finally:
        if session_id:
            _logout(session_id)
        _cleanup_conversations()
        _delete_user(email)


# ---------------------------------------------------------------------------
# TC-002 (AC-074) — reject conversation creation without authentication
# ---------------------------------------------------------------------------


def test_tc002_reject_conversation_creation_without_authentication() -> None:
    _cleanup_conversations()
    try:
        before = _conversation_count()

        resp = client.post("/conversations")

        assert resp.status_code == 401, resp.text

        after = _conversation_count()
        assert after == before, "no conversation should be created for an unauthenticated request"
    finally:
        _cleanup_conversations()


# ---------------------------------------------------------------------------
# TC-003 (AC-074) — new conversation is private to its owner
# ---------------------------------------------------------------------------


def test_tc003_new_conversation_is_private_to_its_owner() -> None:
    alice_email = "us026_tc003_alice@example.com"
    bob_email = "us026_tc003_bob@example.com"
    alice, alice_password = _create_user(alice_email, role="Regular User")
    bob, bob_password = _create_user(bob_email, role="Regular User")
    alice_session_id = ""
    bob_session_id = ""
    try:
        _cleanup_conversations()
        alice_session_id = _login(alice_email, alice_password)
        bob_session_id = _login(bob_email, bob_password)

        create_resp = client.post(
            "/conversations",
            cookies={"session_id": alice_session_id},
        )
        assert create_resp.status_code == 201, create_resp.text
        alice_conversation_id = create_resp.json()["id"]

        conversation = _get_conversation(alice_conversation_id)
        assert conversation.user_id == alice.id

        list_resp = client.get(
            "/conversations",
            cookies={"session_id": bob_session_id},
        )
        assert list_resp.status_code == 200, list_resp.text
        bob_conversations = list_resp.json()
        assert isinstance(bob_conversations, list)
        bob_conversation_ids = {c.get("id") for c in bob_conversations}
        assert alice_conversation_id not in bob_conversation_ids, (
            "bob's conversation list must not include alice's conversation"
        )
    finally:
        if alice_session_id:
            _logout(alice_session_id)
        if bob_session_id:
            _logout(bob_session_id)
        _cleanup_conversations()
        _delete_user(alice_email)
        _delete_user(bob_email)
