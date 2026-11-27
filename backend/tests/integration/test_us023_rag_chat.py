"""Integration tests for POST /chat — RAG retrieval with grounded answers and
citations (US-023).

Covers:
  AC-065 — a relevant question returns a Gemini-generated, grounded answer
           with citations (document ID, filename, page/section, chunk ID).
  AC-067 — when no chunk meets the similarity threshold, no citations are
           fabricated and the fallback path is used instead.
  AC-068 — a question about a Ready document still answers from the
           persisted index after a simulated backend restart.

Follows patterns from test_embeddings.py and test_documents.py: TestClient,
direct DB inserts for fixtures, ``generate_embeddings`` called directly (with
``genai.embed_content`` mocked) to bring a document to Ready status without
a real network call, and ``genai.GenerativeModel.generate_content`` mocked
for the answer-generation step.

Field-name note: the exact JSON shape of the POST /chat and
GET /conversations/{id}/messages responses is inferred from the Citation and
Message model columns used elsewhere in this test kit (document_id,
filename, page_section, chunk_id, content, role) since this sprint's task
does not include the OpenAPI spec. See the task report's ``risk`` field.
"""

from __future__ import annotations

import os
import secrets
import uuid as uuid_mod
from types import SimpleNamespace
from unittest.mock import patch

import bcrypt
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Chunk, Citation, Conversation, Document, Message, Settings, User
from app.processing import generate_embeddings

# Ensure all tables exist on the test database (conftest.py sets DATABASE_URL
# and removes stale DB files before this module is imported).
Base.metadata.create_all(bind=engine)

client = TestClient(app)

_DIM = 768


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hash(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _create_user(email: str, role: str = "Regular User") -> tuple[User, str]:
    """Insert a user directly into the test database; return (user, password)."""
    password = secrets.token_urlsafe(12)
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
    if present:
        os.environ["GEMINI_API_KEY"] = secrets.token_urlsafe(16)
    else:
        os.environ.pop("GEMINI_API_KEY", None)


def _ensure_settings(embedding_model: str = "text-embedding-004") -> None:
    with SessionLocal() as db:
        settings = db.execute(select(Settings).where(Settings.id == 1)).scalar_one_or_none()
        if settings is None:
            settings = Settings(id=1, gemini_embedding_model=embedding_model)
            db.add(settings)
        else:
            settings.gemini_embedding_model = embedding_model
        db.commit()


def _vec(axis: int, dim: int = _DIM) -> list[float]:
    """A unit basis vector along ``axis``. Two vectors on different axes are
    exactly orthogonal (cosine similarity 0), two on the same axis are
    identical (cosine similarity 1), giving deterministic control over which
    chunks a mocked question embedding will or will not match."""
    return [1.0 if i == axis else 0.0 for i in range(dim)]


def _create_document_with_chunks(
    user_id: int,
    filename: str,
    chunk_specs: list[tuple[str, str]],
    status: str = "Processing",
) -> tuple[uuid_mod.UUID, list[uuid_mod.UUID]]:
    """Insert a Document with the given (text, page_section) chunks."""
    with SessionLocal() as db:
        doc = Document(
            filename=filename,
            file_type="PDF",
            file_size=2048,
            file_path=f"/tmp/us023_{uuid_mod.uuid4().hex}.pdf",
            status=status,
            uploaded_by=user_id,
        )
        db.add(doc)
        db.flush()

        chunk_ids: list[uuid_mod.UUID] = []
        for i, (text, page_section) in enumerate(chunk_specs):
            chunk = Chunk(
                document_id=doc.id,
                chunk_text=text,
                chunk_index=i,
                page_section=page_section,
            )
            db.add(chunk)
            db.flush()
            chunk_ids.append(chunk.id)

        db.commit()
        return doc.id, chunk_ids


def _mark_ready(doc_id: uuid_mod.UUID, vector: list[float]) -> None:
    """Embed every chunk of *doc_id* with a fixed vector and bring it to
    Ready status, via the same ``generate_embeddings`` entry point the real
    ingestion pipeline uses (AC-037), with the Gemini SDK mocked out."""
    with patch("app.processing.genai.embed_content") as mock_embed:
        mock_embed.return_value = {"embedding": vector}
        with SessionLocal() as db:
            generate_embeddings(doc_id, db)


def _get_document(doc_id: uuid_mod.UUID) -> Document:
    with SessionLocal() as db:
        return db.execute(select(Document).where(Document.id == doc_id)).scalar_one()


def _get_chunks(doc_id: uuid_mod.UUID) -> list[Chunk]:
    with SessionLocal() as db:
        return list(
            db.execute(
                select(Chunk).where(Chunk.document_id == doc_id).order_by(Chunk.chunk_index)
            ).scalars()
        )


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


def _conversations_count() -> int:
    with SessionLocal() as db:
        return len(db.execute(select(Conversation)).scalars().all())


def _latest_conversation_id(user_id: int) -> int:
    with SessionLocal() as db:
        convo = (
            db.execute(
                select(Conversation)
                .where(Conversation.user_id == user_id)
                .order_by(Conversation.id.desc())
            )
            .scalars()
            .first()
        )
        assert convo is not None, "expected POST /chat to create a conversation for the user"
        return convo.id


def _mock_answer(text: str):
    """A stand-in for the object returned by
    ``genai.GenerativeModel(...).generate_content(...)``, exposing ``.text``
    the way the real Gemini SDK response does."""
    return SimpleNamespace(text=text)


# ---------------------------------------------------------------------------
# TC-035 (AC-065) — grounded answer with full citation fields
# ---------------------------------------------------------------------------


def test_tc035_grounded_answer_with_full_citation_fields() -> None:
    email = "us023_tc035_alice@example.com"
    user, password = _create_user(email, role="Regular User")
    _set_gemini_api_key(present=True)
    _ensure_settings()
    session_id = ""
    try:
        doc_id, chunk_ids = _create_document_with_chunks(
            user.id,
            "Employee_Handbook.pdf",
            [
                (
                    "Employees are entitled to 25 days of annual leave per year, accruing monthly.",
                    "Section 2: Annual Leave Policy",
                ),
                (
                    "Annual leave must be requested at least two weeks in advance "
                    "via the HR portal.",
                    "Section 2: Annual Leave Policy (cont.)",
                ),
            ],
        )
        vector = _vec(0)
        _mark_ready(doc_id, vector)
        assert _get_document(doc_id).status == "Ready"

        session_id = _login(email, password)

        with (
            patch("app.processing.genai.embed_content") as mock_embed,
            patch("google.generativeai.GenerativeModel.generate_content") as mock_generate,
        ):
            mock_embed.return_value = {"embedding": vector}
            mock_generate.return_value = _mock_answer(
                "Employees receive 25 days of annual leave per year, as described "
                "in the Employee Handbook."
            )
            resp = client.post(
                "/chat",
                json={"question": "What is the company's annual leave policy?"},
                cookies={"session_id": session_id},
            )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "citations" in body
        citations = body["citations"]
        assert isinstance(citations, list)
        assert len(citations) >= 1

        chunk_id_strings = {str(c) for c in chunk_ids}
        first = citations[0]
        for key in ("document_id", "filename", "page_section", "chunk_id"):
            assert key in first, f"citation missing '{key}': {first}"
        assert first["document_id"] == str(doc_id)
        assert first["filename"] == "Employee_Handbook.pdf"
        assert first["page_section"]
        assert first["chunk_id"] in chunk_id_strings

        # The body must also include the generated answer text itself.
        answer_text = body.get("content") or body.get("answer")
        assert answer_text, f"no generated answer text found in response: {body}"

        # Post-condition: a new message is stored with the answer and citations.
        with SessionLocal() as db:
            convo = (
                db.execute(select(Conversation).where(Conversation.user_id == user.id))
                .scalars()
                .first()
            )
            assert convo is not None
            messages = (
                db.execute(select(Message).where(Message.conversation_id == convo.id))
                .scalars()
                .all()
            )
            assistant_messages = [m for m in messages if m.role == "assistant"]
            assert len(assistant_messages) >= 1
            latest = max(assistant_messages, key=lambda m: m.id)
            assert latest.content
            stored_citations = (
                db.execute(select(Citation).where(Citation.message_id == latest.id)).scalars().all()
            )
            assert len(stored_citations) >= 1
            assert any(c.document_id == doc_id for c in stored_citations)
    finally:
        if session_id:
            _logout(session_id)
        _cleanup_all()
        _delete_user(email)
        _set_gemini_api_key(present=False)


# ---------------------------------------------------------------------------
# TC-037 (AC-065) — unauthenticated chat request is rejected
# ---------------------------------------------------------------------------


def test_tc037_unauthenticated_chat_request_rejected() -> None:
    _cleanup_all()
    before = _conversations_count()
    try:
        resp = client.post("/chat", json={"question": "What is the refund policy?"})
        assert resp.status_code == 401

        after = _conversations_count()
        assert after == before, "no conversation message should be created for a 401"
    finally:
        _cleanup_all()


# ---------------------------------------------------------------------------
# TC-038 (AC-065 / AC-067) — no fabricated answer/citations below threshold
# ---------------------------------------------------------------------------


def test_tc038_no_fabricated_answer_or_citations_below_threshold() -> None:
    email = "us023_tc038_eve@example.com"
    user, password = _create_user(email, role="Regular User")
    _set_gemini_api_key(present=True)
    _ensure_settings()
    session_id = ""
    try:
        doc_id, _ = _create_document_with_chunks(
            user.id,
            "Employee_Handbook.pdf",
            [
                (
                    "Employees are entitled to 25 days of annual leave per year.",
                    "Section 2: Annual Leave Policy",
                ),
            ],
        )
        handbook_vector = _vec(0)
        _mark_ready(doc_id, handbook_vector)
        assert _get_document(doc_id).status == "Ready"

        session_id = _login(email, password)

        # The question's embedding is orthogonal to the handbook's chunk
        # embedding (cosine similarity 0), so nothing clears the threshold.
        unrelated_vector = _vec(1)

        with (
            patch("app.processing.genai.embed_content") as mock_embed,
            patch("google.generativeai.GenerativeModel.generate_content") as mock_generate,
        ):
            mock_embed.return_value = {"embedding": unrelated_vector}
            mock_generate.return_value = _mock_answer(
                "I could not find relevant information in the knowledge base to "
                "answer this question."
            )
            resp = client.post(
                "/chat",
                json={"question": "What is the recipe for a traditional lasagna?"},
                cookies={"session_id": session_id},
            )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert not body.get("citations"), f"expected no citations, got: {body.get('citations')}"

        answer_text = (body.get("content") or body.get("answer") or "").lower()
        assert "employee_handbook" not in answer_text

        # Post-condition: the stored message has no citations.
        with SessionLocal() as db:
            convo = (
                db.execute(select(Conversation).where(Conversation.user_id == user.id))
                .scalars()
                .first()
            )
            assert convo is not None
            messages = (
                db.execute(select(Message).where(Message.conversation_id == convo.id))
                .scalars()
                .all()
            )
            assistant_messages = [m for m in messages if m.role == "assistant"]
            assert len(assistant_messages) >= 1
            latest = max(assistant_messages, key=lambda m: m.id)
            stored_citations = (
                db.execute(select(Citation).where(Citation.message_id == latest.id)).scalars().all()
            )
            assert len(stored_citations) == 0
    finally:
        if session_id:
            _logout(session_id)
        _cleanup_all()
        _delete_user(email)
        _set_gemini_api_key(present=False)


# ---------------------------------------------------------------------------
# TC-040 (AC-066) — stored message carries full citation detail for display
# ---------------------------------------------------------------------------


def test_tc040_stored_message_includes_citation_detail_for_display() -> None:
    email = "us023_tc040_user@example.com"
    user, password = _create_user(email, role="Regular User")
    _set_gemini_api_key(present=True)
    _ensure_settings()
    session_id = ""
    try:
        doc_id, chunk_ids = _create_document_with_chunks(
            user.id,
            "Employee_Handbook.pdf",
            [
                (
                    "Employees are entitled to 25 days of annual leave per year.",
                    "Section 2: Annual Leave Policy",
                ),
            ],
        )
        vector = _vec(0)
        _mark_ready(doc_id, vector)

        session_id = _login(email, password)

        with (
            patch("app.processing.genai.embed_content") as mock_embed,
            patch("google.generativeai.GenerativeModel.generate_content") as mock_generate,
        ):
            mock_embed.return_value = {"embedding": vector}
            mock_generate.return_value = _mock_answer(
                "Employees get 25 days of annual leave per year."
            )
            chat_resp = client.post(
                "/chat",
                json={"question": "What is the company's annual leave policy?"},
                cookies={"session_id": session_id},
            )
        assert chat_resp.status_code == 200, chat_resp.text

        conversation_id = _latest_conversation_id(user.id)

        resp = client.get(
            f"/conversations/{conversation_id}/messages",
            cookies={"session_id": session_id},
        )
        assert resp.status_code == 200, resp.text
        messages = resp.json()
        assert isinstance(messages, list)
        assistant_messages = [m for m in messages if m.get("role") == "assistant"]
        assert len(assistant_messages) >= 1
        latest = assistant_messages[-1]

        assert "citations" in latest
        assert len(latest["citations"]) >= 1
        chunk_id_strings = {str(c) for c in chunk_ids}
        for citation in latest["citations"]:
            for key in ("document_id", "filename", "page_section", "chunk_id"):
                assert key in citation, f"citation missing '{key}': {citation}"
            assert citation["document_id"] == str(doc_id)
            assert citation["filename"] == "Employee_Handbook.pdf"
            assert citation["page_section"]
            assert citation["chunk_id"] in chunk_id_strings
    finally:
        if session_id:
            _logout(session_id)
        _cleanup_all()
        _delete_user(email)
        _set_gemini_api_key(present=False)


# ---------------------------------------------------------------------------
# TC-041 (AC-067) — citations reference only real, retrieved chunks/documents
# ---------------------------------------------------------------------------


def test_tc041_citations_reference_only_real_documents_and_chunks() -> None:
    email = "us023_tc041_user@example.com"
    user, password = _create_user(email, role="Regular User")
    _set_gemini_api_key(present=True)
    _ensure_settings()
    session_id = ""
    try:
        _cleanup_all()  # precondition: no other documents exist

        handbook_id, handbook_chunk_ids = _create_document_with_chunks(
            user.id,
            "Employee_Handbook.pdf",
            [
                (
                    "How many annual leave days do employees get? 25 days per year.",
                    "Section 2: Annual Leave Policy",
                ),
            ],
        )
        security_id, security_chunk_ids = _create_document_with_chunks(
            user.id,
            "IT_Security_Policy.pdf",
            [
                (
                    "All employees must change their passwords every 90 days.",
                    "Section 5: Password Policy",
                ),
            ],
        )
        handbook_vector = _vec(0)
        security_vector = _vec(1)
        _mark_ready(handbook_id, handbook_vector)
        _mark_ready(security_id, security_vector)

        session_id = _login(email, password)

        with (
            patch("app.processing.genai.embed_content") as mock_embed,
            patch("google.generativeai.GenerativeModel.generate_content") as mock_generate,
        ):
            mock_embed.return_value = {"embedding": handbook_vector}
            mock_generate.return_value = _mock_answer(
                "Employees get 25 annual leave days per year, per the Employee Handbook."
            )
            resp = client.post(
                "/chat",
                json={"question": "How many annual leave days do employees get?"},
                cookies={"session_id": session_id},
            )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        citations = body.get("citations") or []
        assert len(citations) >= 1
        for citation in citations:
            assert "document_id" in citation
            assert "chunk_id" in citation

        first_document_id = citations[0]["document_id"]

        detail_resp = client.get(
            f"/documents/{first_document_id}", cookies={"session_id": session_id}
        )
        assert detail_resp.status_code == 200, detail_resp.text
        assert detail_resp.json()["filename"] == "Employee_Handbook.pdf"

        handbook_chunk_id_strings = {str(c) for c in handbook_chunk_ids}
        security_chunk_id_strings = {str(c) for c in security_chunk_ids}
        for citation in citations:
            assert citation["document_id"] == str(handbook_id)
            assert citation.get("filename") != "IT_Security_Policy.pdf"
            assert citation["document_id"] != str(security_id)
            assert citation["chunk_id"] in handbook_chunk_id_strings
            assert citation["chunk_id"] not in security_chunk_id_strings
    finally:
        if session_id:
            _logout(session_id)
        _cleanup_all()
        _delete_user(email)
        _set_gemini_api_key(present=False)


# ---------------------------------------------------------------------------
# TC-043 (AC-068) — grounded answer from persisted index after restart
# ---------------------------------------------------------------------------


def test_tc043_grounded_answer_from_persisted_index_after_restart() -> None:
    email = "us023_tc043_user@example.com"
    user, password = _create_user(email, role="Regular User")
    _set_gemini_api_key(present=True)
    _ensure_settings()
    session_id = ""
    try:
        doc_id, chunk_ids = _create_document_with_chunks(
            user.id,
            "Employee_Handbook.pdf",
            [
                (
                    "The annual leave entitlement for employees is 25 days per year.",
                    "Section 2: Annual Leave Policy",
                ),
                (
                    "Unused annual leave may be carried over by agreement with a manager.",
                    "Section 2: Annual Leave Policy (cont.)",
                ),
            ],
        )
        vector = _vec(0)
        _mark_ready(doc_id, vector)
        assert _get_document(doc_id).status == "Ready"
        chunks_before = _get_chunks(doc_id)
        assert len(chunks_before) == 2
        assert all(c.embedding is not None and len(c.embedding) == _DIM for c in chunks_before)

        # Simulate a backend restart: drop the pooled connections so the next
        # query must re-open the database file from disk rather than reuse
        # any in-process cache, proving the index is truly persisted.
        engine.dispose()

        session_id = _login(email, password)

        with (
            patch("app.processing.genai.embed_content") as mock_embed,
            patch("google.generativeai.GenerativeModel.generate_content") as mock_generate,
        ):
            mock_embed.return_value = {"embedding": vector}
            mock_generate.return_value = _mock_answer(
                "The annual leave entitlement is 25 days per year, per the Employee Handbook."
            )
            resp = client.post(
                "/chat",
                json={"question": "What is the annual leave entitlement for employees?"},
                cookies={"session_id": session_id},
            )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        citations = body.get("citations") or []
        assert len(citations) >= 1
        assert any(c.get("filename") == "Employee_Handbook.pdf" for c in citations)
        answer_text = body.get("content") or body.get("answer")
        assert answer_text

        # Post-condition: status remains Ready, chunk/embedding counts unchanged.
        doc_after = _get_document(doc_id)
        assert doc_after.status == "Ready"
        chunks_after = _get_chunks(doc_id)
        assert len(chunks_after) == len(chunks_before) == 2
        assert all(c.embedding is not None and len(c.embedding) == _DIM for c in chunks_after)
        assert {c.id for c in chunks_after} == set(chunk_ids)
    finally:
        if session_id:
            _logout(session_id)
        _cleanup_all()
        _delete_user(email)
        _set_gemini_api_key(present=False)
