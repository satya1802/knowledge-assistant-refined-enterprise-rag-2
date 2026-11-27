"""Integration tests for Gemini API/quota error handling (US-025).

Covers:
  AC-072 — a Gemini API error or quota failure during answer generation (on
           POST /chat) or during embedding creation (on document processing)
           surfaces as a clear, readable error rather than a hang or a blank
           page, and no persisted document, chunk, embedding, chat history,
           or user record is lost or corrupted.
  AC-073 — with Gemini as the sole configured AI provider, GET /settings
           exposes only Gemini model configuration, with no Groq-related
           field anywhere in the response.

Follows the patterns of test_us023_rag_chat.py and test_us024_gemini_fallback.py
(TestClient, direct DB inserts for fixtures, login for session cookies,
``app.services.genai`` patched for the chat flow) and of test_embeddings.py
for the embedding-failure path (``app.processing.genai.embed_content``
patched, ``generate_embeddings`` called directly).

Risk: the real document pipeline chunks a freshly uploaded file and embeds
it through a queued background worker; no Redis/RQ worker runs in this test
sandbox (see test_embeddings.py's own docstring, which calls
``generate_embeddings`` directly for the same reason). TC-030 therefore
uploads the file through POST /documents exactly as the case describes,
inserts the chunk the real pipeline would have produced, and then invokes
``generate_embeddings`` directly with the Gemini SDK mocked to fail -- the
same substitution the kit's own US-013 suite makes -- to reach the Failed
state the case polls GET /documents/{id} for.
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
    """Insert a user directly into the test database; return (user, password).

    The password is generated at run time -- never a literal -- since it
    stands in for a credential.
    """
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


def _ensure_settings(cosine_threshold: float = 0.62) -> None:
    with SessionLocal() as db:
        settings = db.execute(select(Settings).where(Settings.id == 1)).scalar_one_or_none()
        if settings is None:
            settings = Settings(id=1, cosine_threshold=cosine_threshold)
            db.add(settings)
        else:
            settings.cosine_threshold = cosine_threshold
        db.commit()


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


def _failing_model(error_message: str) -> MagicMock:
    """A stand-in for ``genai.GenerativeModel(...)`` whose
    ``generate_content(...)`` raises, the way the real Gemini SDK does on a
    quota/API error."""
    model = MagicMock()
    model.generate_content.side_effect = RuntimeError(error_message)
    return model


def _create_conversation(session_id: str) -> str:
    resp = client.post("/conversations", cookies={"session_id": session_id})
    assert resp.status_code in (200, 201), resp.text
    body = resp.json()
    conversation_id = body.get("id") or body.get("conversation_id")
    assert conversation_id, f"expected a conversation id in the response, got: {body}"
    return conversation_id


def _get_messages(conversation_id: str, session_id: str) -> list[dict]:
    resp = client.get(
        f"/conversations/{conversation_id}/messages",
        cookies={"session_id": session_id},
    )
    assert resp.status_code == 200, resp.text
    messages = resp.json()
    assert isinstance(messages, list)
    return messages


def _simplify(messages: list[dict]) -> list[tuple]:
    """Reduce a message list to its user-visible (role, content) pairs, so a
    comparison across two calls isn't thrown off by incidental metadata."""
    return [(m.get("role"), m.get("content")) for m in messages]


def _create_ready_document(user_id: int, filename: str) -> uuid_mod.UUID:
    """Insert a Document that is already Ready, with one embedded chunk."""
    with SessionLocal() as db:
        doc = Document(
            filename=filename,
            file_type="PDF",
            file_size=4096,
            file_path=f"/tmp/us025_{uuid_mod.uuid4().hex}.pdf",
            status="Ready",
            uploaded_by=user_id,
        )
        db.add(doc)
        db.flush()
        chunk = Chunk(
            document_id=doc.id,
            chunk_text="Existing handbook content, already embedded.",
            chunk_index=0,
            page_section="Section 1",
            embedding=[0.0] * _DIM,
        )
        db.add(chunk)
        db.commit()
        return doc.id


# ---------------------------------------------------------------------------
# TC-029 (AC-072) — Gemini error during answer generation: clear error,
# no data loss in the new or a pre-existing conversation
# ---------------------------------------------------------------------------


def test_tc029_gemini_answer_error_returns_clear_error_without_data_loss() -> None:
    email = "us025_tc029_user@example.com"
    user, password = _create_user(email)
    _set_gemini_api_key(present=True)
    _ensure_settings()
    session_id = ""
    try:
        _cleanup_all()
        session_id = _login(email, password)

        # Precondition: conversation A already has a question and an answer.
        conversation_a_id = _create_conversation(session_id)
        with (
            patch("app.services.genai.embed_content") as mock_embed,
            patch("app.services.genai.GenerativeModel") as mock_cls,
        ):
            mock_embed.return_value = {"embedding": [0.0] * _DIM}
            mock_cls.return_value = _mock_model("Our standard return window is 30 days.")
            setup_resp = client.post(
                "/chat",
                json={
                    "conversation_id": conversation_a_id,
                    "question": "What is your standard return policy?",
                },
                cookies={"session_id": session_id},
            )
        assert setup_resp.status_code == 200, setup_resp.text

        messages_a_before = _get_messages(conversation_a_id, session_id)
        assert len(messages_a_before) == 2
        assert any(
            m.get("role") == "user" and m.get("content") == "What is your standard return policy?"
            for m in messages_a_before
        )
        assert any(
            m.get("role") == "assistant"
            and m.get("content") == "Our standard return window is 30 days."
            for m in messages_a_before
        )

        # Step 1: create conversation B.
        conversation_b_id = _create_conversation(session_id)

        # Step 2: POST /chat on conversation B, with Gemini simulated to
        # return a quota-exceeded error for this next answer-generation call.
        with (
            patch("app.services.genai.embed_content") as mock_embed,
            patch("app.services.genai.GenerativeModel") as mock_cls,
        ):
            mock_embed.return_value = {"embedding": [0.0] * _DIM}
            mock_cls.return_value = _failing_model(
                "429 Resource exhausted: quota exceeded for generateContent"
            )
            chat_resp = client.post(
                "/chat",
                json={
                    "conversation_id": conversation_b_id,
                    "question": "What is the refund policy for enterprise customers?",
                },
                cookies={"session_id": session_id},
            )

        assert chat_resp.status_code != 200, (
            "a Gemini quota/API error must not be reported as a success: got "
            f"{chat_resp.status_code} {chat_resp.text}"
        )
        assert 500 <= chat_resp.status_code < 600, (
            "expected a clear server-side error status for the failed AI "
            f"service call, got: {chat_resp.status_code} {chat_resp.text}"
        )
        error_body = chat_resp.json()
        message = error_body.get("detail") or error_body.get("message") or error_body.get("error")
        assert message, f"expected a readable error message, got: {error_body}"
        assert isinstance(message, str) and message.strip()
        assert "traceback" not in message.lower()

        # Step 3: conversation B still exists, with no corrupted/partial message.
        messages_b = _get_messages(conversation_b_id, session_id)
        for m in messages_b:
            if m.get("role") == "assistant":
                assert m.get("content"), f"found a corrupted/partial assistant message: {m}"

        # Step 4: conversation A's pre-existing history is unaffected.
        messages_a_after = _get_messages(conversation_a_id, session_id)
        assert _simplify(messages_a_after) == _simplify(messages_a_before)
    finally:
        if session_id:
            _logout(session_id)
        _cleanup_all()
        _delete_user(email)
        _set_gemini_api_key(present=False)


# ---------------------------------------------------------------------------
# TC-030 (AC-072) — Gemini error during embedding creation: Failed with a
# readable reason, uploaded file retained, unrelated documents unaffected
# ---------------------------------------------------------------------------


def test_tc030_gemini_embedding_error_preserves_file_and_other_docs() -> None:
    admin_email = "us025_tc030_admin@example.com"
    admin, admin_password = _create_user(admin_email, role="Administrator")
    _set_gemini_api_key(present=True)
    _ensure_settings()
    session_id = ""
    try:
        _cleanup_all()

        existing_doc_id = _create_ready_document(admin.id, "existing-handbook.pdf")

        session_id = _login(admin_email, admin_password)

        # Step 1: upload a new file.
        content = b"%PDF-1.4\n" + (b"A" * (2 * 1024 * 1024 - 9))
        upload_resp = client.post(
            "/documents",
            files={"file": ("policy-handbook.pdf", content)},
            cookies={"session_id": session_id},
        )
        assert upload_resp.status_code == 200, upload_resp.text
        upload_body = upload_resp.json()
        assert upload_body["status"] == "Processing"
        new_doc_id = upload_body["id"]
        new_doc_uuid = uuid_mod.UUID(str(new_doc_id))

        # The real pipeline chunks the file and embeds it through a queued
        # background worker; no such worker runs in this test sandbox (see
        # the module docstring's risk note). A chunk is inserted the way the
        # pipeline would have produced it, and `generate_embeddings` is
        # called directly -- the same substitution test_embeddings.py makes
        # for US-013 -- with the Gemini SDK mocked to fail.
        with SessionLocal() as db:
            chunk = Chunk(
                document_id=new_doc_uuid,
                chunk_text="Policy handbook introduction paragraph.",
                chunk_index=0,
                page_section="Section 1",
            )
            db.add(chunk)
            db.commit()

        with patch("app.processing.genai.embed_content") as mock_embed:
            mock_embed.side_effect = RuntimeError("429 Resource exhausted: quota exceeded")
            with SessionLocal() as db:
                generate_embeddings(new_doc_uuid, db)

        # Step 2: GET /documents/{id}, polled until processing finishes.
        detail_body: dict = {}
        for _ in range(10):
            detail_resp = client.get(f"/documents/{new_doc_id}", cookies={"session_id": session_id})
            assert detail_resp.status_code == 200, detail_resp.text
            detail_body = detail_resp.json()
            if detail_body["status"] != "Processing":
                break
        assert detail_body["status"] == "Failed", (
            f"expected the document to end up Failed with a readable reason, got: {detail_body}"
        )
        assert detail_body.get("failure_reason"), (
            f"expected a readable failure reason for the embedding error, got: {detail_body}"
        )
        reason = detail_body["failure_reason"].lower()
        assert "quota" in reason or "exceeded" in reason or "429" in reason, (
            f"failure_reason does not reference the embedding error: {reason}"
        )

        # Step 3: existing-handbook.pdf is unaffected by the new failure.
        list_resp = client.get("/documents", cookies={"session_id": session_id})
        assert list_resp.status_code == 200, list_resp.text
        items = list_resp.json()
        existing_item = next((i for i in items if i["id"] == str(existing_doc_id)), None)
        assert existing_item is not None, "existing-handbook.pdf disappeared from GET /documents"
        assert existing_item["status"] == "Ready"

        # Step 4: the originally uploaded file for the new document is
        # still downloadable.
        download_resp = client.get(
            f"/documents/{new_doc_id}/download", cookies={"session_id": session_id}
        )
        assert download_resp.status_code == 200, download_resp.text
        assert download_resp.content == content
    finally:
        if session_id:
            _logout(session_id)
        _cleanup_all()
        _delete_user(admin_email)
        _set_gemini_api_key(present=False)


# ---------------------------------------------------------------------------
# TC-033 (AC-073) — settings confirm Gemini as the sole configured provider
# ---------------------------------------------------------------------------


def test_tc033_settings_confirm_gemini_as_sole_configured_ai_provider() -> None:
    admin_email = "us025_tc033_admin@example.com"
    admin, admin_password = _create_user(admin_email, role="Administrator")
    session_id = ""
    try:
        session_id = _login(admin_email, admin_password)

        resp = client.get("/settings", cookies={"session_id": session_id})
        assert resp.status_code == 200, resp.text
        body = resp.json()

        assert "gemini_answer_model" in body
        assert "gemini_embedding_model" in body
        assert "cosine_threshold" in body
        assert "cookie_secure_flag" in body

        forbidden_keys = {"groq_api_key", "groq_model", "groq_provider", "groq_embedding_model"}
        leaked_keys = forbidden_keys & set(body.keys())
        assert not leaked_keys, f"Groq-related settings leaked in response: {leaked_keys}"
        for key in body.keys():
            assert "groq" not in key.lower(), f"a Groq-related field name was found: {key}"

        raw = resp.text.lower()
        assert "groq" not in raw, f"found a Groq-related reference in /settings: {resp.text}"
    finally:
        if session_id:
            _logout(session_id)
        _delete_user(admin_email)
