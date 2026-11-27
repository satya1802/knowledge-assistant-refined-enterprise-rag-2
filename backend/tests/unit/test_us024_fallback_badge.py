"""Unit tests for the Gemini general-knowledge fallback badge (US-024):
POST /chat.

Covers:
  AC-069 — when cosine similarity search returns no chunks meeting the live
           threshold, Gemini answers from general knowledge (no retrieved
           context in the prompt) and the response is flagged so the UI can
           show the 'Not from your documents' badge (``is_fallback: true``).
  AC-071 — no fabricated citations are included on a fallback answer;
           citations only appear when real chunks are retrieved.

This reuses the RAG flow built for US-023 (``app.services.answer_chat_question``,
``generate_fallback_answer``) and the ``Message.is_fallback`` / ``ChatResponse``
contract already in place; these tests pin the fallback-specific behaviour
this story adds on top, rather than re-implement it.

The Gemini SDK (``app.services.genai``) is patched throughout so no network
access is required.
"""

from __future__ import annotations

import os
import secrets
import uuid as uuid_mod
from unittest.mock import MagicMock, patch

import bcrypt
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import SessionLocal
from app.main import app
from app.models import Chunk, Citation, Conversation, Document, Message, Settings, User
from app.services import generate_fallback_answer

client = TestClient(app)

_DIM = 768


# ---------------------------------------------------------------------------
# Helpers (mirrors backend/tests/unit/test_chat_rag.py)
# ---------------------------------------------------------------------------


def _set_gemini_api_key(present: bool = True) -> None:
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


def _mock_generative_model(answer_text: str = "A general-knowledge answer.") -> MagicMock:
    model = MagicMock()
    model.generate_content.return_value = MagicMock(text=answer_text)
    return model


# ---------------------------------------------------------------------------
# AC-069 — Gemini answers from general knowledge; response flagged for badge
# ---------------------------------------------------------------------------


class TestAc069FallbackGeneralKnowledge:
    def setup_method(self) -> None:
        _set_gemini_api_key(present=True)
        self.user = _create_user("us024_ac069@example.com", secrets.token_urlsafe(12))
        _ensure_settings(cosine_threshold=0.9)
        # The only indexed chunk is orthogonal to the query, so similarity
        # search returns no chunk meeting the threshold.
        self.doc_id, self.chunk_ids = _create_ready_document(
            self.user.id, [("unrelated handbook text", _basis_vector(1), "p.1")]
        )

    def teardown_method(self) -> None:
        _cleanup()
        _delete_user("us024_ac069@example.com")
        _set_gemini_api_key(present=False)

    def test_ac069_fallback_prompt_carries_no_retrieved_context(self) -> None:
        """Gemini answers from general knowledge: the prompt is the bare
        question, with no retrieved-chunk context mixed in."""
        with SessionLocal() as db:
            with patch("app.services.genai.GenerativeModel") as mock_cls:
                model = _mock_generative_model("General knowledge answer.")
                mock_cls.return_value = model
                answer = generate_fallback_answer("What is the capital of France?", db)

        prompt = model.generate_content.call_args.args[0]
        assert prompt == "What is the capital of France?"
        assert "unrelated handbook text" not in prompt
        assert answer == "General knowledge answer."

    def test_ac069_chat_response_flags_fallback_for_the_badge(self) -> None:
        """When no chunk meets the threshold, the chat response is flagged
        ``is_fallback: true`` so the UI can render the 'Not from your
        documents' badge alongside the answer."""
        email = "us024_ac069_chat@example.com"
        password = secrets.token_urlsafe(12)
        user = _create_user(email, password)
        session_id = _login(email, password)
        conversation_id = _create_conversation(user.id)
        try:
            with (
                patch("app.services.genai.embed_content") as mock_embed,
                patch("app.services.genai.GenerativeModel") as mock_cls,
            ):
                mock_embed.return_value = {"embedding": _basis_vector(0)}
                mock_cls.return_value = _mock_generative_model("Paris is the capital of France.")

                resp = client.post(
                    "/chat",
                    json={
                        "conversation_id": str(conversation_id),
                        "question": "What is the capital of France?",
                    },
                    cookies={"session_id": session_id},
                )

            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["is_fallback"] is True
            assert body["answer"] == "Paris is the capital of France."
        finally:
            client.post("/auth/logout", cookies={"session_id": session_id})
            _delete_user(email)

    def test_ac069_persisted_assistant_message_is_flagged_fallback(self) -> None:
        """The persisted ``Message`` row carries ``is_fallback=True`` too,
        not just the response body, so the badge survives a reload of the
        conversation history."""
        email = "us024_ac069_persist@example.com"
        password = secrets.token_urlsafe(12)
        user = _create_user(email, password)
        session_id = _login(email, password)
        conversation_id = _create_conversation(user.id)
        try:
            with (
                patch("app.services.genai.embed_content") as mock_embed,
                patch("app.services.genai.GenerativeModel") as mock_cls,
            ):
                mock_embed.return_value = {"embedding": _basis_vector(0)}
                mock_cls.return_value = _mock_generative_model("General knowledge reply.")

                client.post(
                    "/chat",
                    json={"conversation_id": str(conversation_id), "question": "Anything?"},
                    cookies={"session_id": session_id},
                )

            with SessionLocal() as db:
                assistant_message = db.execute(
                    select(Message).where(
                        Message.conversation_id == conversation_id, Message.role == "assistant"
                    )
                ).scalar_one()
                assert assistant_message.is_fallback is True
        finally:
            client.post("/auth/logout", cookies={"session_id": session_id})
            _delete_user(email)


# ---------------------------------------------------------------------------
# AC-071 — no fabricated citations; citations only for real retrieved chunks
# ---------------------------------------------------------------------------


class TestAc071NoFabricatedCitations:
    def setup_method(self) -> None:
        _set_gemini_api_key(present=True)
        self.email = "us024_ac071@example.com"
        self.password = secrets.token_urlsafe(12)
        self.user = _create_user(self.email, self.password)
        self.session_id = _login(self.email, self.password)
        self.conversation_id = _create_conversation(self.user.id)

    def teardown_method(self) -> None:
        client.post("/auth/logout", cookies={"session_id": self.session_id})
        _cleanup()
        _delete_user(self.email)
        _set_gemini_api_key(present=False)

    def test_ac071_no_chunks_found_yields_empty_citations_in_response(self) -> None:
        """No relevant chunks exist at all (no document indexed): the
        response carries no citations."""
        _ensure_settings(cosine_threshold=0.5)
        with (
            patch("app.services.genai.embed_content") as mock_embed,
            patch("app.services.genai.GenerativeModel") as mock_cls,
        ):
            mock_embed.return_value = {"embedding": _basis_vector(0)}
            mock_cls.return_value = _mock_generative_model("No KB match, general answer.")

            resp = client.post(
                "/chat",
                json={"conversation_id": str(self.conversation_id), "question": "Anything?"},
                cookies={"session_id": self.session_id},
            )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["is_fallback"] is True
        assert body["citations"] == []

    def test_ac071_no_citation_rows_persisted_for_fallback_message(self) -> None:
        """No ``Citation`` rows are written to the database for a fallback
        answer -- the absence of citations is not just a response detail,
        there is nothing fabricated in storage either."""
        _ensure_settings(cosine_threshold=0.5)
        with (
            patch("app.services.genai.embed_content") as mock_embed,
            patch("app.services.genai.GenerativeModel") as mock_cls,
        ):
            mock_embed.return_value = {"embedding": _basis_vector(0)}
            mock_cls.return_value = _mock_generative_model("General answer.")

            client.post(
                "/chat",
                json={"conversation_id": str(self.conversation_id), "question": "Anything?"},
                cookies={"session_id": self.session_id},
            )

        with SessionLocal() as db:
            assistant_message = db.execute(
                select(Message).where(
                    Message.conversation_id == self.conversation_id, Message.role == "assistant"
                )
            ).scalar_one()
            citations = (
                db.execute(select(Citation).where(Citation.message_id == assistant_message.id))
                .scalars()
                .all()
            )
            assert citations == []

    def test_ac071_citations_appear_only_when_a_real_chunk_is_retrieved(self) -> None:
        """Contrast case: once a real chunk meets the threshold, the exact
        same conversation starts returning citations -- they are not
        permanently suppressed, only absent when nothing was retrieved."""
        _ensure_settings(cosine_threshold=0.5)
        doc_id, chunk_ids = _create_ready_document(
            self.user.id,
            [("Our refund window is 30 days.", _basis_vector(0), "p.4")],
            filename="policy.pdf",
        )

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
        body = resp.json()
        assert body["is_fallback"] is False
        assert len(body["citations"]) == 1
        assert body["citations"][0]["document_id"] == str(doc_id)
        assert body["citations"][0]["chunk_id"] == str(chunk_ids[0])
