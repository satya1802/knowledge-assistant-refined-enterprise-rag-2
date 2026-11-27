"""Unit tests for US-025: Gemini API error handling in the chat flow.

Covers:
  AC-072 — a Gemini API error or quota failure during answer generation or
           embedding creation (question embedding, grounded-answer
           generation, or fallback-answer generation) is surfaced as a
           clear, structured error (``CHAT_GEMINI_UNAVAILABLE``, 503)
           rather than an unhandled crash, and every already-persisted
           document, chunk, embedding, message, and user is left intact.
  AC-073 — Gemini is the sole AI provider: no Groq remnant exists in the
           backend's dependencies or configuration.

The Gemini SDK (``app.services.genai``) is patched throughout so no network
access is required, following the fixture patterns of
backend/tests/unit/test_chat_rag.py.
"""

from __future__ import annotations

import os
import secrets
import uuid as uuid_mod
from pathlib import Path
from unittest.mock import patch

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import SessionLocal
from app.errors import CHAT_GEMINI_UNAVAILABLE
from app.main import app
from app.models import Chunk, Citation, Conversation, Document, Message, Settings, User
from app.services import (
    GeminiUnavailableError,
    embed_question,
    generate_fallback_answer,
    generate_grounded_answer,
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
    vec = [0.0] * dim
    vec[index] = 1.0
    return vec


def _ensure_settings(cosine_threshold: float = 0.5) -> None:
    with SessionLocal() as db:
        settings = db.execute(select(Settings).where(Settings.id == 1)).scalar_one_or_none()
        if settings is None:
            settings = Settings(id=1, cosine_threshold=cosine_threshold)
            db.add(settings)
        else:
            settings.cosine_threshold = cosine_threshold
        db.commit()


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
) -> tuple[uuid_mod.UUID, list[uuid_mod.UUID]]:
    with SessionLocal() as db:
        doc = Document(
            filename=filename,
            file_type="PDF",
            file_size=100,
            file_path=f"/tmp/{filename}",
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


def _add_message(conversation_id: uuid_mod.UUID, role: str, content: str) -> uuid_mod.UUID:
    with SessionLocal() as db:
        message = Message(conversation_id=conversation_id, role=role, content=content)
        db.add(message)
        db.commit()
        db.refresh(message)
        return message.id


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


# ---------------------------------------------------------------------------
# AC-072 — service-level: each Gemini call raises GeminiUnavailableError
# ---------------------------------------------------------------------------


class TestAc072ServiceLayerRaisesGeminiUnavailable:
    def setup_method(self) -> None:
        _set_gemini_api_key(present=True)
        self.user = _create_user("us025_service@example.com", "pw-12345")
        _ensure_settings(cosine_threshold=0.5)
        self.doc_id, self.chunk_ids = _create_ready_document(
            self.user.id, [("Our refund window is 30 days.", _basis_vector(0), "p.4")]
        )

    def teardown_method(self) -> None:
        _cleanup()
        _delete_user("us025_service@example.com")
        _set_gemini_api_key(present=False)

    def test_ac072_embed_question_wraps_quota_error(self) -> None:
        """A quota failure from embed_content surfaces as GeminiUnavailableError."""
        with SessionLocal() as db, patch("app.services.genai.embed_content") as mock_embed:
            mock_embed.side_effect = Exception("429 Resource exhausted: quota exceeded")
            with pytest.raises(GeminiUnavailableError):
                embed_question("Refund policy?", db)

    def test_ac072_embed_question_missing_api_key_raises_gemini_unavailable(self) -> None:
        _set_gemini_api_key(present=False)
        with SessionLocal() as db:
            with pytest.raises(GeminiUnavailableError):
                embed_question("Refund policy?", db)

    def test_ac072_grounded_answer_wraps_api_error(self) -> None:
        with SessionLocal() as db:
            chunk = db.execute(select(Chunk).where(Chunk.id == self.chunk_ids[0])).scalar_one()
            with patch("app.services.genai.GenerativeModel") as mock_cls:
                mock_cls.side_effect = Exception("503 Service unavailable")
                with pytest.raises(GeminiUnavailableError):
                    generate_grounded_answer("What is the refund window?", [chunk], db)

    def test_ac072_fallback_answer_wraps_api_error(self) -> None:
        with SessionLocal() as db:
            with patch("app.services.genai.GenerativeModel") as mock_cls:
                mock_cls.side_effect = Exception("429 quota exceeded")
                with pytest.raises(GeminiUnavailableError):
                    generate_fallback_answer("Unrelated question?", db)


# ---------------------------------------------------------------------------
# AC-072 — POST /chat: a Gemini error during embedding surfaces as a clear,
# structured error without data loss
# ---------------------------------------------------------------------------


class TestAc072ChatEndpointEmbeddingError:
    def setup_method(self) -> None:
        _set_gemini_api_key(present=True)
        self.email = "us025_chat_embed@example.com"
        self.password = secrets.token_urlsafe(12)
        self.user = _create_user(self.email, self.password)
        self.session_id = _login(self.email, self.password)
        _ensure_settings(cosine_threshold=0.5)
        self.doc_id, self.chunk_ids = _create_ready_document(
            self.user.id,
            [("Our refund window is 30 days.", _basis_vector(0), "p.4")],
            filename="policy.pdf",
        )
        self.conversation_id = _create_conversation(self.user.id)
        self.prior_message_id = _add_message(
            self.conversation_id, "assistant", "Earlier answer that must survive."
        )

    def teardown_method(self) -> None:
        client.post("/auth/logout", cookies={"session_id": self.session_id})
        _cleanup()
        _delete_user(self.email)
        _set_gemini_api_key(present=False)

    def test_ac072_embedding_error_returns_clear_structured_error(self) -> None:
        """A quota/API error while embedding the question returns 503 with
        the agreed detail, not an unhandled 500."""
        with patch("app.services.genai.embed_content") as mock_embed:
            mock_embed.side_effect = Exception("429 Resource exhausted")

            resp = client.post(
                "/chat",
                json={"conversation_id": str(self.conversation_id), "question": "Refund policy?"},
                cookies={"session_id": self.session_id},
            )

        assert resp.status_code == CHAT_GEMINI_UNAVAILABLE.status_code, resp.text
        assert resp.json()["detail"] == CHAT_GEMINI_UNAVAILABLE.detail

    def test_ac072_no_new_message_or_citation_persisted_on_embedding_error(self) -> None:
        """No partial user/assistant message or citation is left behind."""
        with patch("app.services.genai.embed_content") as mock_embed:
            mock_embed.side_effect = Exception("429 Resource exhausted")
            client.post(
                "/chat",
                json={"conversation_id": str(self.conversation_id), "question": "Refund policy?"},
                cookies={"session_id": self.session_id},
            )

        with SessionLocal() as db:
            messages = (
                db.execute(select(Message).where(Message.conversation_id == self.conversation_id))
                .scalars()
                .all()
            )
            # Only the pre-existing assistant message from setup remains.
            assert len(messages) == 1
            assert messages[0].id == self.prior_message_id
            assert messages[0].content == "Earlier answer that must survive."

    def test_ac072_existing_documents_and_chunks_remain_intact(self) -> None:
        """Persisted documents, chunks, and their embeddings are untouched."""
        with patch("app.services.genai.embed_content") as mock_embed:
            mock_embed.side_effect = Exception("quota exceeded")
            client.post(
                "/chat",
                json={"conversation_id": str(self.conversation_id), "question": "Refund policy?"},
                cookies={"session_id": self.session_id},
            )

        with SessionLocal() as db:
            doc = db.execute(select(Document).where(Document.id == self.doc_id)).scalar_one()
            assert doc.status == "Ready"
            chunk = db.execute(select(Chunk).where(Chunk.id == self.chunk_ids[0])).scalar_one()
            assert chunk.embedding is not None
            assert chunk.chunk_text == "Our refund window is 30 days."

    def test_ac072_user_record_remains_intact(self) -> None:
        with patch("app.services.genai.embed_content") as mock_embed:
            mock_embed.side_effect = Exception("quota exceeded")
            client.post(
                "/chat",
                json={"conversation_id": str(self.conversation_id), "question": "Refund policy?"},
                cookies={"session_id": self.session_id},
            )

        with SessionLocal() as db:
            user = db.execute(select(User).where(User.id == self.user.id)).scalar_one()
            assert user.email == self.email


# ---------------------------------------------------------------------------
# AC-072 — POST /chat: a Gemini error during grounded answer generation
# ---------------------------------------------------------------------------


class TestAc072ChatEndpointGroundedGenerationError:
    def setup_method(self) -> None:
        _set_gemini_api_key(present=True)
        self.email = "us025_chat_grounded_err@example.com"
        self.password = secrets.token_urlsafe(12)
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

    def test_ac072_answer_generation_error_returns_clear_structured_error(self) -> None:
        with (
            patch("app.services.genai.embed_content") as mock_embed,
            patch("app.services.genai.GenerativeModel") as mock_cls,
        ):
            mock_embed.return_value = {"embedding": _basis_vector(0)}
            mock_cls.side_effect = Exception("500 internal error from Gemini")

            resp = client.post(
                "/chat",
                json={"conversation_id": str(self.conversation_id), "question": "Refund policy?"},
                cookies={"session_id": self.session_id},
            )

        assert resp.status_code == CHAT_GEMINI_UNAVAILABLE.status_code, resp.text
        assert resp.json()["detail"] == CHAT_GEMINI_UNAVAILABLE.detail

    def test_ac072_no_citation_or_message_persisted_on_generation_error(self) -> None:
        with (
            patch("app.services.genai.embed_content") as mock_embed,
            patch("app.services.genai.GenerativeModel") as mock_cls,
        ):
            mock_embed.return_value = {"embedding": _basis_vector(0)}
            mock_cls.side_effect = Exception("500 internal error from Gemini")

            client.post(
                "/chat",
                json={"conversation_id": str(self.conversation_id), "question": "Refund policy?"},
                cookies={"session_id": self.session_id},
            )

        with SessionLocal() as db:
            messages = (
                db.execute(select(Message).where(Message.conversation_id == self.conversation_id))
                .scalars()
                .all()
            )
            assert messages == []
            citations = db.execute(select(Citation)).scalars().all()
            assert citations == []


# ---------------------------------------------------------------------------
# AC-072 — POST /chat: a Gemini error during fallback answer generation
# (no chunk met the threshold, and the fallback call itself fails)
# ---------------------------------------------------------------------------


class TestAc072ChatEndpointFallbackGenerationError:
    def setup_method(self) -> None:
        _set_gemini_api_key(present=True)
        self.email = "us025_chat_fallback_err@example.com"
        self.password = secrets.token_urlsafe(12)
        self.user = _create_user(self.email, self.password)
        self.session_id = _login(self.email, self.password)
        _ensure_settings(cosine_threshold=0.9)
        self.doc_id, self.chunk_ids = _create_ready_document(
            self.user.id, [("unrelated chunk", _basis_vector(1), "p.1")]
        )
        self.conversation_id = _create_conversation(self.user.id)

    def teardown_method(self) -> None:
        client.post("/auth/logout", cookies={"session_id": self.session_id})
        _cleanup()
        _delete_user(self.email)
        _set_gemini_api_key(present=False)

    def test_ac072_fallback_generation_error_returns_clear_structured_error(self) -> None:
        with (
            patch("app.services.genai.embed_content") as mock_embed,
            patch("app.services.genai.GenerativeModel") as mock_cls,
        ):
            # Question embedding succeeds but matches nothing above the
            # threshold, so the fallback path is taken -- and it is the
            # fallback Gemini call itself that fails here.
            mock_embed.return_value = {"embedding": _basis_vector(0)}
            mock_cls.side_effect = Exception("429 quota exceeded")

            resp = client.post(
                "/chat",
                json={
                    "conversation_id": str(self.conversation_id),
                    "question": "Something unrelated?",
                },
                cookies={"session_id": self.session_id},
            )

        assert resp.status_code == CHAT_GEMINI_UNAVAILABLE.status_code, resp.text
        assert resp.json()["detail"] == CHAT_GEMINI_UNAVAILABLE.detail

        with SessionLocal() as db:
            messages = (
                db.execute(select(Message).where(Message.conversation_id == self.conversation_id))
                .scalars()
                .all()
            )
            assert messages == []


# ---------------------------------------------------------------------------
# AC-073 — Gemini is the sole AI provider: no Groq remnant in the backend
# ---------------------------------------------------------------------------


class TestAc073NoGroqRemnant:
    def test_ac073_requirements_txt_has_no_groq_dependency(self) -> None:
        requirements = Path("requirements.txt").read_text(encoding="utf-8")
        assert "groq" not in requirements.lower()

    def test_ac073_env_example_has_no_groq_variable(self) -> None:
        env_example = Path(".env.example").read_text(encoding="utf-8")
        assert "groq" not in env_example.lower()

    def test_ac073_no_groq_reference_anywhere_in_app_source(self) -> None:
        app_dir = Path("app")
        offenders = [
            str(path)
            for path in app_dir.rglob("*.py")
            if "groq" in path.read_text(encoding="utf-8").lower()
        ]
        assert offenders == [], f"Groq remnant found in: {offenders}"
