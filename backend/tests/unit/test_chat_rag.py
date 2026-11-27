"""Unit tests for the RAG chat flow (US-023): POST /chat.

Covers:
  AC-065 — relevant chunks (cosine similarity >= the live threshold) are
           retrieved, Gemini generates a grounded answer from them, and the
           response includes citations (document ID, filename, page/section,
           chunk ID).
  AC-067 — the answer is grounded in the retrieved chunks; when no chunk
           meets the threshold, the fallback answer carries no citations
           (no fabricated citations).
  AC-068 — a question about a Ready document is answered from the persisted
           chunk/embedding rows, with no re-embedding or re-upload needed —
           i.e. after a simulated page refresh / backend restart.

The Gemini SDK (``app.services.genai``) is patched throughout so no network
access is required. Follows the fixture patterns of test_documents.py and
test_settings.py: TestClient, direct DB inserts, login for session cookies.
"""

from __future__ import annotations

import os
import secrets
import uuid as uuid_mod
from unittest.mock import MagicMock, patch

import bcrypt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import DATABASE_URL, SessionLocal
from app.main import app
from app.models import Chunk, Citation, Conversation, Document, Message, Settings, User
from app.services import (
    generate_fallback_answer,
    generate_grounded_answer,
    retrieve_relevant_chunks,
)

client = TestClient(app)

_DIM = 768


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _hash(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _create_user(email: str, password: str, role: str = "Regular User") -> User:
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
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.cookies.get("session_id") or ""


def _basis_vector(index: int, dim: int = _DIM) -> list[float]:
    """A unit vector with a 1.0 at *index* and 0.0 elsewhere.

    Two basis vectors at different indices are orthogonal (cosine similarity
    0.0); the same index gives cosine similarity 1.0 — this makes the
    threshold boundary exact and easy to assert on.
    """
    vec = [0.0] * dim
    vec[index] = 1.0
    return vec


def _create_conversation(user_id: int, title: str = "Test conversation") -> uuid_mod.UUID:
    with SessionLocal() as db:
        conversation = Conversation(user_id=user_id, title=title)
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        return conversation.id


def _create_ready_document(
    user_id: int,
    chunks: list[tuple[str, list[float] | None, str | None]],
    *,
    filename: str = "handbook.pdf",
    status: str = "Ready",
) -> tuple[uuid_mod.UUID, list[uuid_mod.UUID]]:
    """Insert a Document with the given (text, embedding, page_section) chunks."""
    with SessionLocal() as db:
        doc = Document(
            filename=filename,
            file_type="PDF",
            file_size=100,
            file_path=f"/tmp/{filename}",
            status=status,
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


def _ensure_settings(cosine_threshold: float = 0.5) -> None:
    with SessionLocal() as db:
        settings = db.execute(select(Settings).where(Settings.id == 1)).scalar_one_or_none()
        if settings is None:
            settings = Settings(id=1, cosine_threshold=cosine_threshold)
            db.add(settings)
        else:
            settings.cosine_threshold = cosine_threshold
        db.commit()


def _cleanup() -> None:
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


def _mock_generative_model(answer_text: str = "The answer, grounded in the sources.") -> MagicMock:
    model = MagicMock()
    model.generate_content.return_value = MagicMock(text=answer_text)
    return model


# ---------------------------------------------------------------------------
# AC-065 — retrieval by cosine-similarity threshold
# ---------------------------------------------------------------------------


class TestRetrievalThreshold:
    def setup_method(self) -> None:
        self.user = _create_user("us023_retrieval@example.com", "pw-12345")
        _ensure_settings(cosine_threshold=0.5)
        self.doc_id, self.chunk_ids = _create_ready_document(
            self.user.id,
            [
                ("matching chunk", _basis_vector(0), "p.1"),
                ("unrelated chunk", _basis_vector(1), "p.2"),
            ],
        )

    def teardown_method(self) -> None:
        _cleanup()
        _delete_user("us023_retrieval@example.com")

    def test_chunk_at_or_above_threshold_is_retrieved(self) -> None:
        """AC-065: cosine similarity >= threshold is retrieved."""
        with SessionLocal() as db:
            results = retrieve_relevant_chunks(_basis_vector(0), db)

        assert len(results) == 1
        chunk, score = results[0]
        assert chunk.id == self.chunk_ids[0]
        assert score == 1.0

    def test_chunk_below_threshold_is_excluded(self) -> None:
        """AC-065/AC-067: an orthogonal (cosine 0.0) chunk never matches,
        so it cannot be cited."""
        with SessionLocal() as db:
            results = retrieve_relevant_chunks(_basis_vector(0), db)

        retrieved_ids = {chunk.id for chunk, _score in results}
        assert self.chunk_ids[1] not in retrieved_ids

    def test_results_sorted_by_similarity_descending(self) -> None:
        """AC-065: the best-matching chunks come first."""
        _ensure_settings(cosine_threshold=0.0)
        with SessionLocal() as db:
            results = retrieve_relevant_chunks(_basis_vector(0), db)

        scores = [score for _chunk, score in results]
        assert scores == sorted(scores, reverse=True)

    def test_chunks_of_non_ready_documents_are_excluded(self) -> None:
        """Only the persisted index of Ready documents is searched."""
        processing_doc_id, processing_chunk_ids = _create_ready_document(
            self.user.id,
            [("processing chunk", _basis_vector(0), "p.1")],
            filename="still-processing.pdf",
            status="Processing",
        )
        try:
            with SessionLocal() as db:
                results = retrieve_relevant_chunks(_basis_vector(0), db)
            retrieved_ids = {chunk.id for chunk, _score in results}
            assert processing_chunk_ids[0] not in retrieved_ids
        finally:
            with SessionLocal() as db:
                doc = db.execute(
                    select(Document).where(Document.id == processing_doc_id)
                ).scalar_one()
                db.delete(doc)
                db.commit()


# ---------------------------------------------------------------------------
# AC-065 / AC-067 — grounded vs. fallback answer generation
# ---------------------------------------------------------------------------


class TestAnswerGeneration:
    def setup_method(self) -> None:
        _set_gemini_api_key(present=True)
        self.user = _create_user("us023_answer@example.com", "pw-12345")
        _ensure_settings(cosine_threshold=0.5)
        self.doc_id, self.chunk_ids = _create_ready_document(
            self.user.id, [("Our refund window is 30 days.", _basis_vector(0), "p.4")]
        )

    def teardown_method(self) -> None:
        _cleanup()
        _delete_user("us023_answer@example.com")
        _set_gemini_api_key(present=False)

    def test_grounded_answer_prompt_contains_retrieved_chunk_text(self) -> None:
        """AC-065/AC-067: the prompt passed to Gemini is built from the
        retrieved chunks, not invented."""
        with SessionLocal() as db:
            chunk = db.execute(select(Chunk).where(Chunk.id == self.chunk_ids[0])).scalar_one()
            with patch("app.services.genai.GenerativeModel") as mock_cls:
                model = _mock_generative_model()
                mock_cls.return_value = model
                answer = generate_grounded_answer("What is the refund window?", [chunk], db)

        prompt = model.generate_content.call_args.args[0]
        assert "Our refund window is 30 days." in prompt
        assert answer == "The answer, grounded in the sources."

    def test_grounded_answer_uses_configured_model(self) -> None:
        """AC-065: the model name comes from Settings.gemini_answer_model."""
        with SessionLocal() as db:
            settings = db.execute(select(Settings).where(Settings.id == 1)).scalar_one()
            settings.gemini_answer_model = "custom-answer-model"
            db.commit()

            chunk = db.execute(select(Chunk).where(Chunk.id == self.chunk_ids[0])).scalar_one()
            with patch("app.services.genai.GenerativeModel") as mock_cls:
                mock_cls.return_value = _mock_generative_model()
                generate_grounded_answer("question", [chunk], db)

        assert mock_cls.call_args.args[0] == "models/custom-answer-model"

    def test_fallback_answer_prompt_has_no_retrieved_context(self) -> None:
        """AC-067: a fallback answer is not built from any chunk context."""
        with SessionLocal() as db:
            with patch("app.services.genai.GenerativeModel") as mock_cls:
                model = _mock_generative_model("General knowledge answer.")
                mock_cls.return_value = model
                answer = generate_fallback_answer("What is the refund window?", db)

        prompt = model.generate_content.call_args.args[0]
        assert "Our refund window is 30 days." not in prompt
        assert answer == "General knowledge answer."


# ---------------------------------------------------------------------------
# POST /chat — end to end: grounded answer with citations (AC-065, AC-067)
# ---------------------------------------------------------------------------


class TestChatEndpointGrounded:
    def setup_method(self) -> None:
        _set_gemini_api_key(present=True)
        self.email = "us023_chat_grounded@example.com"
        self.password = "pw-12345"
        self.user = _create_user(self.email, self.password)
        self.session_id = _login(self.email, self.password)
        _ensure_settings(cosine_threshold=0.5)
        self.doc_id, self.chunk_ids = _create_ready_document(
            self.user.id,
            [("Our refund window is 30 days.", _basis_vector(0), "p.4")],
            filename="policy.pdf",
        )
        self.conversation_id = _create_conversation(self.user.id)

    def teardown_method(self) -> None:
        client.post("/auth/logout", cookies={"session_id": self.session_id})
        _cleanup()
        _delete_user(self.email)
        _set_gemini_api_key(present=False)

    def test_grounded_answer_includes_full_citation(self) -> None:
        """AC-065: the response includes a citation with document ID,
        filename, page/section, and chunk ID."""
        with (
            patch("app.services.genai.embed_content") as mock_embed,
            patch("app.services.genai.GenerativeModel") as mock_cls,
        ):
            mock_embed.return_value = {"embedding": _basis_vector(0)}
            mock_cls.return_value = _mock_generative_model("Refunds are allowed within 30 days.")

            resp = client.post(
                "/chat",
                json={"conversation_id": str(self.conversation_id), "question": "Refund policy?"},
                cookies={"session_id": self.session_id},
            )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["is_fallback"] is False
        assert body["answer"] == "Refunds are allowed within 30 days."
        assert len(body["citations"]) == 1
        citation = body["citations"][0]
        assert citation["document_id"] == str(self.doc_id)
        assert citation["filename"] == "policy.pdf"
        assert citation["page_section"] == "p.4"
        assert citation["chunk_id"] == str(self.chunk_ids[0])

    def test_grounded_answer_and_citations_are_persisted(self) -> None:
        """AC-065: the message and its citations are persisted, not just
        returned in the response."""
        with (
            patch("app.services.genai.embed_content") as mock_embed,
            patch("app.services.genai.GenerativeModel") as mock_cls,
        ):
            mock_embed.return_value = {"embedding": _basis_vector(0)}
            mock_cls.return_value = _mock_generative_model("Refunds within 30 days.")

            resp = client.post(
                "/chat",
                json={"conversation_id": str(self.conversation_id), "question": "Refund policy?"},
                cookies={"session_id": self.session_id},
            )
        assert resp.status_code == 200, resp.text

        with SessionLocal() as db:
            messages = (
                db.execute(select(Message).where(Message.conversation_id == self.conversation_id))
                .scalars()
                .all()
            )
            assert any(m.role == "user" and m.content == "Refund policy?" for m in messages)
            assistant_messages = [m for m in messages if m.role == "assistant"]
            assert len(assistant_messages) == 1
            assert assistant_messages[0].is_fallback is False

            citations = (
                db.execute(select(Citation).where(Citation.message_id == assistant_messages[0].id))
                .scalars()
                .all()
            )
            assert len(citations) == 1
            assert citations[0].document_id == self.doc_id
            assert citations[0].chunk_id == self.chunk_ids[0]


# ---------------------------------------------------------------------------
# POST /chat — no relevant chunks: fallback with no citations (AC-067)
# ---------------------------------------------------------------------------


class TestChatEndpointFallback:
    def setup_method(self) -> None:
        _set_gemini_api_key(present=True)
        self.email = "us023_chat_fallback@example.com"
        self.password = "pw-12345"
        self.user = _create_user(self.email, self.password)
        self.session_id = _login(self.email, self.password)
        _ensure_settings(cosine_threshold=0.9)
        # The only chunk is orthogonal to the query embedding, so it never
        # meets the threshold.
        self.doc_id, self.chunk_ids = _create_ready_document(
            self.user.id, [("unrelated chunk", _basis_vector(1), "p.1")]
        )
        self.conversation_id = _create_conversation(self.user.id)

    def teardown_method(self) -> None:
        client.post("/auth/logout", cookies={"session_id": self.session_id})
        _cleanup()
        _delete_user(self.email)
        _set_gemini_api_key(present=False)

    def test_no_relevant_chunk_returns_fallback_without_citations(self) -> None:
        """AC-067: no fabricated citations on a fallback answer."""
        with (
            patch("app.services.genai.embed_content") as mock_embed,
            patch("app.services.genai.GenerativeModel") as mock_cls,
        ):
            mock_embed.return_value = {"embedding": _basis_vector(0)}
            mock_cls.return_value = _mock_generative_model("I don't have that in the KB.")

            resp = client.post(
                "/chat",
                json={
                    "conversation_id": str(self.conversation_id),
                    "question": "Something unrelated?",
                },
                cookies={"session_id": self.session_id},
            )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["is_fallback"] is True
        assert body["citations"] == []

    def test_fallback_message_persisted_with_no_citations(self) -> None:
        with (
            patch("app.services.genai.embed_content") as mock_embed,
            patch("app.services.genai.GenerativeModel") as mock_cls,
        ):
            mock_embed.return_value = {"embedding": _basis_vector(0)}
            mock_cls.return_value = _mock_generative_model("General answer.")

            client.post(
                "/chat",
                json={
                    "conversation_id": str(self.conversation_id),
                    "question": "Something unrelated?",
                },
                cookies={"session_id": self.session_id},
            )

        with SessionLocal() as db:
            assistant_message = db.execute(
                select(Message).where(
                    Message.conversation_id == self.conversation_id, Message.role == "assistant"
                )
            ).scalar_one()
            assert assistant_message.is_fallback is True
            citations = (
                db.execute(select(Citation).where(Citation.message_id == assistant_message.id))
                .scalars()
                .all()
            )
            assert citations == []


# ---------------------------------------------------------------------------
# POST /chat — validation and conversation lookup
# ---------------------------------------------------------------------------


class TestChatValidation:
    def setup_method(self) -> None:
        self.email = "us023_chat_validation@example.com"
        self.password = "pw-12345"
        self.user = _create_user(self.email, self.password)
        self.session_id = _login(self.email, self.password)
        self.conversation_id = _create_conversation(self.user.id)

    def teardown_method(self) -> None:
        client.post("/auth/logout", cookies={"session_id": self.session_id})
        _cleanup()
        _delete_user(self.email)

    def test_rejects_empty_question(self) -> None:
        resp = client.post(
            "/chat",
            json={"conversation_id": str(self.conversation_id), "question": "   "},
            cookies={"session_id": self.session_id},
        )
        assert resp.status_code == 422

    def test_unknown_conversation_returns_404(self) -> None:
        resp = client.post(
            "/chat",
            json={"conversation_id": str(uuid_mod.uuid4()), "question": "Anything?"},
            cookies={"session_id": self.session_id},
        )
        assert resp.status_code == 404

    def test_other_users_conversation_returns_404(self) -> None:
        other_email = "us023_chat_other_user@example.com"
        other_user = _create_user(other_email, "pw-12345")
        other_conversation_id = _create_conversation(other_user.id)
        try:
            resp = client.post(
                "/chat",
                json={"conversation_id": str(other_conversation_id), "question": "Anything?"},
                cookies={"session_id": self.session_id},
            )
            assert resp.status_code == 404
        finally:
            _delete_user(other_email)

    def test_unauthenticated_returns_401(self) -> None:
        client.cookies.clear()
        resp = client.post(
            "/chat",
            json={"conversation_id": str(self.conversation_id), "question": "Anything?"},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# AC-068 — persisted index is used after a simulated restart
# ---------------------------------------------------------------------------


class TestPersistedIndexAcrossRestart:
    def setup_method(self) -> None:
        _set_gemini_api_key(present=True)
        self.email = "us023_chat_restart@example.com"
        self.password = "pw-12345"
        self.user = _create_user(self.email, self.password)
        self.session_id = _login(self.email, self.password)
        _ensure_settings(cosine_threshold=0.5)
        self.conversation_id = _create_conversation(self.user.id)

    def teardown_method(self) -> None:
        client.post("/auth/logout", cookies={"session_id": self.session_id})
        _cleanup()
        _delete_user(self.email)
        _set_gemini_api_key(present=False)

    def test_answer_comes_from_persisted_chunks_without_reembedding_document(self) -> None:
        """AC-068: a document embedded and marked Ready in a prior process is
        answered from its persisted chunk rows -- no re-upload, no
        re-embedding of the document's chunks, only the question is embedded.

        The document's chunks are inserted through a brand-new engine/session
        bound to the same database file, simulating that they were produced
        by a process that has since exited (a restart), rather than created
        in-process right before the request.
        """
        new_engine = create_engine(
            DATABASE_URL,
            connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
            future=True,
        )
        new_session_factory = sessionmaker(bind=new_engine, autoflush=False, expire_on_commit=False)

        with new_session_factory() as db:
            doc = Document(
                filename="restart-survivor.pdf",
                file_type="PDF",
                file_size=42,
                file_path="/tmp/restart-survivor.pdf",
                status="Ready",
                uploaded_by=self.user.id,
            )
            db.add(doc)
            db.flush()
            chunk = Chunk(
                document_id=doc.id,
                chunk_text="The warranty lasts two years.",
                chunk_index=0,
                page_section="p.9",
                embedding=_basis_vector(2),
            )
            db.add(chunk)
            db.commit()
            doc_id, chunk_id = doc.id, chunk.id
        new_engine.dispose()

        with (
            patch("app.services.genai.embed_content") as mock_embed,
            patch("app.services.genai.GenerativeModel") as mock_cls,
        ):
            mock_embed.return_value = {"embedding": _basis_vector(2)}
            mock_cls.return_value = _mock_generative_model("Two years.")

            resp = client.post(
                "/chat",
                json={
                    "conversation_id": str(self.conversation_id),
                    "question": "How long is the warranty?",
                },
                cookies={"session_id": self.session_id},
            )

            # Only the question is embedded here -- the document's chunk
            # embedding came from the persisted row, not a fresh call.
            assert mock_embed.call_count == 1
            assert mock_embed.call_args.kwargs["content"] == "How long is the warranty?"

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["is_fallback"] is False
        assert body["answer"] == "Two years."
        assert len(body["citations"]) == 1
        assert body["citations"][0]["document_id"] == str(doc_id)
        assert body["citations"][0]["chunk_id"] == str(chunk_id)
