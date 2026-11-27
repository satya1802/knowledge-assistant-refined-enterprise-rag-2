"""Integration tests for POST /chat — Gemini general-knowledge fallback with
a "Not from your documents" badge (US-024).

Covers:
  AC-069 — when cosine similarity search returns no chunks meeting the
           threshold, Gemini answers from general knowledge and the
           response carries a fallback indicator.
  AC-070 — the fallback status is recorded on the stored assistant message
           (and exposed through the conversation history), so the UI can
           render the badge.
  AC-071 — no fabricated citations accompany a fallback answer; citations
           only appear when real chunks are retrieved and used to ground
           the answer.

Field-name note: this task does not include the OpenAPI spec. The exact
JSON shape of POST /chat and GET /conversations/{id}/messages is taken from
backend/tests/unit/test_chat_rag.py (US-023, same endpoints), which asserts
on ``conversation_id``/``question`` in the request and ``is_fallback`` /
``answer`` / ``citations`` (each with ``document_id``, ``filename``,
``page_section``, ``chunk_id``) in the response, and from
backend/tests/integration/test_us023_rag_chat.py for the same shape via
GET /conversations/{id}/messages. See the task report's ``risk`` field.
"""

from __future__ import annotations

import os
import secrets
import uuid as uuid_mod
from unittest.mock import MagicMock, patch

import bcrypt
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Chunk, Citation, Conversation, Document, Message, Settings, User

# Ensure all tables exist on the test database (conftest.py sets DATABASE_URL
# and removes stale DB files before this module is imported).
Base.metadata.create_all(bind=engine)

client = TestClient(app)

_DIM = 768
_THRESHOLD = 0.62


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hash(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _create_user(email: str, role: str = "Regular User") -> tuple[User, str]:
    """Insert a user directly into the test database; return (user, password)."""
    password = secrets.token_urlsafe(16)
    with SessionLocal() as db:
        user = User(email=email, password_hash=_hash(password), role=role)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user, password


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


def _set_gemini_api_key(present: bool = True) -> None:
    """Set or remove the GEMINI_API_KEY env var for the duration of a test.

    The value is generated at run time (never a literal) since it stands in
    for a credential; the Gemini SDK itself is patched in every test, so the
    value is never actually sent anywhere.
    """
    if present:
        os.environ["GEMINI_API_KEY"] = secrets.token_urlsafe(16)
    else:
        os.environ.pop("GEMINI_API_KEY", None)


def _ensure_settings(cosine_threshold: float = _THRESHOLD) -> None:
    with SessionLocal() as db:
        settings = db.execute(select(Settings).where(Settings.id == 1)).scalar_one_or_none()
        if settings is None:
            settings = Settings(id=1, cosine_threshold=cosine_threshold)
            db.add(settings)
        else:
            settings.cosine_threshold = cosine_threshold
        db.commit()


def _basis_vector(axis: int, dim: int = _DIM) -> list[float]:
    """A unit vector with a 1.0 at *axis*. Two basis vectors on the same axis
    are identical (cosine similarity 1.0); on different axes they are
    exactly orthogonal (cosine similarity 0.0)."""
    vec = [0.0] * dim
    vec[axis] = 1.0
    return vec


def _partial_vector(cosine_similarity: float, dim: int = _DIM) -> list[float]:
    """A unit vector whose cosine similarity against ``_basis_vector(0)`` is
    exactly *cosine_similarity*, by construction: lets a chunk be made
    "loosely related" (below the threshold) without relying on chance."""
    remainder = (1.0 - cosine_similarity**2) ** 0.5
    vec = [0.0] * dim
    vec[0] = cosine_similarity
    vec[1] = remainder
    return vec


def _create_ready_document(
    user_id: int,
    chunks: list[tuple[str, list[float], str]],
    filename: str = "handbook.pdf",
) -> tuple[uuid_mod.UUID, list[uuid_mod.UUID]]:
    """Insert a Ready Document with the given (text, embedding, page_section)
    chunks, mirroring backend/tests/unit/test_chat_rag.py's
    ``_create_ready_document``."""
    with SessionLocal() as db:
        doc = Document(
            filename=filename,
            file_type="PDF",
            file_size=1024,
            file_path=f"/tmp/us024_{uuid_mod.uuid4().hex}.pdf",
            status="Ready",
            uploaded_by=user_id,
        )
        db.add(doc)
        db.flush()

        chunk_ids: list[uuid_mod.UUID] = []
        for i, (text, embedding, page_section) in enumerate(chunks):
            chunk = Chunk(
                document_id=doc.id,
                chunk_text=text,
                chunk_index=i,
                page_section=page_section,
                embedding=embedding,
            )
            db.add(chunk)
            db.flush()
            chunk_ids.append(chunk.id)

        db.commit()
        return doc.id, chunk_ids


def _cleanup_all() -> None:
    """Remove citations, messages, conversations, chunks and documents."""
    with SessionLocal() as db:
        for citation in db.execute(select(Citation)).scalars().all():
            db.delete(citation)
        for message in db.execute(select(Message)).scalars().all():
            db.delete(message)
        for conversation in db.execute(select(Conversation)).scalars().all():
            db.delete(conversation)
        for chunk in db.execute(select(Chunk)).scalars().all():
            db.delete(chunk)
        for doc in db.execute(select(Document)).scalars().all():
            db.delete(doc)
        db.commit()


def _mock_model(answer_text: str) -> MagicMock:
    """A stand-in for ``genai.GenerativeModel(...)``, exposing
    ``.generate_content(...).text`` the way the real Gemini SDK does."""
    model = MagicMock()
    model.generate_content.return_value = MagicMock(text=answer_text)
    return model


def _create_conversation(session_id: str) -> str:
    resp = client.post("/conversations", cookies={"session_id": session_id})
    assert resp.status_code in (200, 201), resp.text
    body = resp.json()
    conversation_id = body.get("id") or body.get("conversation_id")
    assert conversation_id, f"expected a conversation id in the response, got: {body}"
    return conversation_id


def _get_assistant_message(conversation_id: str, session_id: str) -> dict:
    resp = client.get(
        f"/conversations/{conversation_id}/messages",
        cookies={"session_id": session_id},
    )
    assert resp.status_code == 200, resp.text
    messages = resp.json()
    assistant_messages = [m for m in messages if m.get("role") == "assistant"]
    assert assistant_messages, f"expected an assistant message, got: {messages}"
    return assistant_messages[-1]


# ---------------------------------------------------------------------------
# TC-015 (AC-069) — fallback answer when no chunks meet the threshold
# ---------------------------------------------------------------------------


def test_tc015_fallback_answer_returned_when_no_chunks_meet_threshold() -> None:
    email = "us024_tc015_user@example.com"
    user, password = _create_user(email)
    _set_gemini_api_key(present=True)
    _ensure_settings()
    session_id = ""
    try:
        _cleanup_all()  # precondition: the Knowledge Base is empty

        session_id = _login(email, password)
        conversation_id = _create_conversation(session_id)

        with (
            patch("app.services.genai.embed_content") as mock_embed,
            patch("app.services.genai.GenerativeModel") as mock_cls,
        ):
            mock_embed.return_value = {"embedding": _basis_vector(0)}
            mock_cls.return_value = _mock_model(
                "Mercury boils at about 356.7 degrees Celsius; this does not "
                "change from one planet to another."
            )
            resp = client.post(
                "/chat",
                json={
                    "conversation_id": conversation_id,
                    "question": "What is the boiling point of mercury on Mars?",
                },
                cookies={"session_id": session_id},
            )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["is_fallback"] is True
        answer_text = body.get("answer")
        assert answer_text, f"expected a general-knowledge answer, got: {body}"

        assistant_message = _get_assistant_message(conversation_id, session_id)
        assert assistant_message.get("is_fallback") is True
    finally:
        if session_id:
            _logout(session_id)
        _cleanup_all()
        _delete_user(email)
        _set_gemini_api_key(present=False)


# ---------------------------------------------------------------------------
# TC-017 (AC-069) — fallback when existing chunks score below the threshold
# ---------------------------------------------------------------------------


def test_tc017_fallback_triggers_when_chunks_score_below_threshold() -> None:
    email = "us024_tc017_user@example.com"
    user, password = _create_user(email)
    _set_gemini_api_key(present=True)
    _ensure_settings()
    session_id = ""
    try:
        _cleanup_all()

        # Loosely related: cosine similarity 0.4 against the question
        # embedding below, which is well under the 0.62 threshold.
        _create_ready_document(
            user.id,
            [
                (
                    "Many seabirds travel long distances between breeding "
                    "grounds, though this overview does not cover any "
                    "particular species' migration route.",
                    _partial_vector(0.4),
                    "Section 1: Seabird Overview",
                ),
            ],
            filename="Seabird_Overview.pdf",
        )

        session_id = _login(email, password)
        conversation_id = _create_conversation(session_id)

        with (
            patch("app.services.genai.embed_content") as mock_embed,
            patch("app.services.genai.GenerativeModel") as mock_cls,
        ):
            mock_embed.return_value = {"embedding": _basis_vector(0)}
            mock_cls.return_value = _mock_model(
                "Arctic terns migrate from the Arctic to the Antarctic and "
                "back again each year, one of the longest migrations of any "
                "animal."
            )
            resp = client.post(
                "/chat",
                json={
                    "conversation_id": conversation_id,
                    "question": "Describe the migratory patterns of Arctic terns",
                },
                cookies={"session_id": session_id},
            )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["is_fallback"] is True
        assert body.get("citations") == []

        assistant_message = _get_assistant_message(conversation_id, session_id)
        assert assistant_message.get("is_fallback") is True
        assert assistant_message.get("citations") == []
    finally:
        if session_id:
            _logout(session_id)
        _cleanup_all()
        _delete_user(email)
        _set_gemini_api_key(present=False)


# ---------------------------------------------------------------------------
# TC-018 (AC-070) — fallback status retrievable from stored messages
# ---------------------------------------------------------------------------


def test_tc018_fallback_status_is_retrievable_from_stored_messages() -> None:
    email = "us024_tc018_user@example.com"
    user, password = _create_user(email)
    _set_gemini_api_key(present=True)
    _ensure_settings()
    session_id = ""
    try:
        _cleanup_all()

        _create_ready_document(
            user.id,
            [
                (
                    "Our quarterly sales figures are reviewed every January.",
                    _basis_vector(1),
                    "Section 3: Sales Reporting",
                ),
            ],
            filename="Sales_Reporting.pdf",
        )

        session_id = _login(email, password)
        conversation_id = _create_conversation(session_id)

        with (
            patch("app.services.genai.embed_content") as mock_embed,
            patch("app.services.genai.GenerativeModel") as mock_cls,
        ):
            mock_embed.return_value = {"embedding": _basis_vector(0)}
            mock_cls.return_value = _mock_model(
                "I do not have a record of a 2050 World Cup; my knowledge "
                "has a cutoff before that date."
            )
            resp = client.post(
                "/chat",
                json={
                    "conversation_id": conversation_id,
                    "question": "Who won the football World Cup in 2050?",
                },
                cookies={"session_id": session_id},
            )

        assert resp.status_code == 200, resp.text
        assert resp.json()["is_fallback"] is True

        assistant_message = _get_assistant_message(conversation_id, session_id)
        assert assistant_message.get("is_fallback") is True
    finally:
        if session_id:
            _logout(session_id)
        _cleanup_all()
        _delete_user(email)
        _set_gemini_api_key(present=False)


# ---------------------------------------------------------------------------
# TC-020 (AC-071) — no citations in a fallback answer
# ---------------------------------------------------------------------------


def test_tc020_no_citations_included_in_fallback_answer() -> None:
    email = "us024_tc020_user@example.com"
    user, password = _create_user(email)
    _set_gemini_api_key(present=True)
    _ensure_settings()
    session_id = ""
    try:
        _cleanup_all()

        _create_ready_document(
            user.id,
            [
                (
                    "Our office relocation is scheduled for next quarter.",
                    _basis_vector(1),
                    "Section 7: Facilities",
                ),
            ],
            filename="Facilities_Update.pdf",
        )

        session_id = _login(email, password)
        conversation_id = _create_conversation(session_id)

        with (
            patch("app.services.genai.embed_content") as mock_embed,
            patch("app.services.genai.GenerativeModel") as mock_cls,
        ):
            mock_embed.return_value = {"embedding": _basis_vector(0)}
            mock_cls.return_value = _mock_model(
                "Mercury boils at about 356.7 degrees Celsius regardless of which planet it is on."
            )
            resp = client.post(
                "/chat",
                json={
                    "conversation_id": conversation_id,
                    "question": "What is the boiling point of mercury on Mars?",
                },
                cookies={"session_id": session_id},
            )

        assert resp.status_code == 200, resp.text
        assert resp.json()["is_fallback"] is True

        assistant_message = _get_assistant_message(conversation_id, session_id)
        assert assistant_message.get("citations") == []
    finally:
        if session_id:
            _logout(session_id)
        _cleanup_all()
        _delete_user(email)
        _set_gemini_api_key(present=False)


# ---------------------------------------------------------------------------
# TC-021 (AC-071) — citations included when real chunks are retrieved
# ---------------------------------------------------------------------------


def test_tc021_citations_included_when_real_chunks_are_retrieved() -> None:
    email = "us024_tc021_user@example.com"
    user, password = _create_user(email)
    _set_gemini_api_key(present=True)
    _ensure_settings()
    session_id = ""
    try:
        _cleanup_all()

        doc_id, _chunk_ids = _create_ready_document(
            user.id,
            [
                (
                    "Employees are entitled to 25 days of annual leave per year.",
                    _basis_vector(0),
                    "Section 2: Annual Leave Policy",
                ),
            ],
            filename="Employee_Handbook.pdf",
        )

        session_id = _login(email, password)
        conversation_id = _create_conversation(session_id)

        with (
            patch("app.services.genai.embed_content") as mock_embed,
            patch("app.services.genai.GenerativeModel") as mock_cls,
        ):
            mock_embed.return_value = {"embedding": _basis_vector(0)}
            mock_cls.return_value = _mock_model(
                "Employees receive 25 days of annual leave per year, per the Employee Handbook."
            )
            resp = client.post(
                "/chat",
                json={
                    "conversation_id": conversation_id,
                    "question": "What is the annual leave policy?",
                },
                cookies={"session_id": session_id},
            )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["is_fallback"] is False
        citations = body.get("citations") or []
        assert len(citations) >= 1
        assert any(c.get("document_id") == str(doc_id) for c in citations)

        assistant_message = _get_assistant_message(conversation_id, session_id)
        assert assistant_message.get("is_fallback") is False
        message_citations = assistant_message.get("citations") or []
        assert len(message_citations) >= 1
        assert any(c.get("document_id") == str(doc_id) for c in message_citations)
    finally:
        if session_id:
            _logout(session_id)
        _cleanup_all()
        _delete_user(email)
        _set_gemini_api_key(present=False)
