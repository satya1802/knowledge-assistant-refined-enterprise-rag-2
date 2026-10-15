"""Unit tests for the Gemini embedding-generation step (US-013).

Covers:
  AC-035 — each chunk gets a 768-dimensional embedding via the Gemini API,
           persisted alongside the chunk record, using the model name from
           Settings.
  AC-036 — on Gemini API error or missing key, document status → Failed
           with a readable failure_reason; chunks and already-persisted
           embeddings are retained, nothing deleted.
  AC-037 — when all chunks have embeddings, document status → Ready.

These tests live inside ``backend/app/`` because the task scope restricts
writes to that directory.  They replicate the test-database bootstrap that
``backend/tests/conftest.py`` performs so they can run standalone with
``pytest backend/app/test_processing.py``.

External calls (``genai.configure`` and ``genai.embed_content``) are patched
so no network access is required.
"""

from __future__ import annotations

import os
import uuid as uuid_mod
from pathlib import Path
from unittest.mock import patch

# Point at a throwaway database and remove any pre-existing files BEFORE
# importing the application (which creates tables at import time).
os.environ["DATABASE_URL"] = "sqlite:///./test_processing.db"
for _name in ("app.db", "test_processing.db"):
    _p = Path(_name)
    if _p.exists():
        _p.unlink()

import bcrypt  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import Chunk, Document, Settings, User  # noqa: F401,E402  # registers tables
from app.processing import generate_embeddings  # noqa: E402

# Ensure all tables exist on the throwaway database.
Base.metadata.create_all(bind=engine)

_DIM = 768


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hash(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _create_user(email: str, password: str = "pw-123", role: str = "Administrator") -> User:
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


def _create_document_with_chunks(
    user_id: int,
    chunk_texts: list[str],
    status: str = "Processing",
) -> tuple[uuid_mod.UUID, list[uuid_mod.UUID]]:
    """Insert a Document with the given chunk texts and return (doc_id, chunk_ids)."""
    with SessionLocal() as db:
        doc = Document(
            filename="test.txt",
            file_type="TXT",
            file_size=100,
            file_path="/tmp/test.txt",
            status=status,
            uploaded_by=user_id,
        )
        db.add(doc)
        db.flush()

        chunk_ids: list[uuid_mod.UUID] = []
        for i, text in enumerate(chunk_texts):
            chunk = Chunk(
                document_id=doc.id,
                chunk_text=text,
                chunk_index=i,
            )
            db.add(chunk)
            db.flush()
            chunk_ids.append(chunk.id)

        db.commit()
        return doc.id, chunk_ids


def _cleanup_documents() -> None:
    with SessionLocal() as db:
        docs = db.execute(select(Document)).scalars().all()
        for d in docs:
            db.delete(d)
        db.commit()


def _fake_embedding(dim: int = _DIM) -> list[float]:
    """Return a deterministic fake embedding vector of the given dimension."""
    return [float(i) for i in range(dim)]


def _set_gemini_api_key(present: bool = True) -> None:
    """Set or remove the GEMINI_API_KEY env var for the duration of a test."""
    if present:
        os.environ["GEMINI_API_KEY"] = "test-api-key"
    else:
        os.environ.pop("GEMINI_API_KEY", None)


def _ensure_settings(embedding_model: str = "text-embedding-004") -> None:
    """Ensure the singleton Settings row exists with the given embedding model."""
    with SessionLocal() as db:
        settings = db.execute(select(Settings).where(Settings.id == 1)).scalar_one_or_none()
        if settings is None:
            settings = Settings(id=1, gemini_embedding_model=embedding_model)
            db.add(settings)
        else:
            settings.gemini_embedding_model = embedding_model
        db.commit()


# ---------------------------------------------------------------------------
# AC-035 — each chunk gets a 768-dim embedding via the Gemini API
# ---------------------------------------------------------------------------


class TestEmbeddingSuccess:
    def setup_method(self) -> None:
        _set_gemini_api_key(present=True)
        _ensure_settings()
        self.user = _create_user("us013_success@example.com")
        self.doc_id, self.chunk_ids = _create_document_with_chunks(
            self.user.id, ["chunk one", "chunk two", "chunk three"]
        )

    def teardown_method(self) -> None:
        _cleanup_documents()
        _delete_user("us013_success@example.com")
        _set_gemini_api_key(present=False)

    def test_all_chunks_get_768_dim_embeddings(self) -> None:
        """AC-035: each chunk receives a 768-dimensional embedding."""
        with patch("app.processing.genai.embed_content") as mock_embed:
            mock_embed.return_value = {"embedding": _fake_embedding()}

            with SessionLocal() as db:
                generate_embeddings(self.doc_id, db)

        with SessionLocal() as db:
            chunks = list(
                db.execute(
                    select(Chunk)
                    .where(Chunk.document_id == self.doc_id)
                    .order_by(Chunk.chunk_index)
                ).scalars()
            )
            assert len(chunks) == 3
            for chunk in chunks:
                assert chunk.embedding is not None
                assert len(chunk.embedding) == _DIM

    def test_embed_content_called_with_configured_model(self) -> None:
        """AC-035: the model name comes from Settings.gemini_embedding_model."""
        _ensure_settings(embedding_model="text-embedding-004")

        with patch("app.processing.genai.embed_content") as mock_embed:
            mock_embed.return_value = {"embedding": _fake_embedding()}
            with SessionLocal() as db:
                generate_embeddings(self.doc_id, db)

        # Every call uses the model name from Settings (prefixed with models/).
        for call in mock_embed.call_args_list:
            assert call.kwargs["model"] == "models/text-embedding-004"
            assert call.kwargs["output_dimensionality"] == _DIM

    def test_embed_content_called_once_per_chunk(self) -> None:
        """AC-035: genai.embed_content is called once per chunk."""
        with patch("app.processing.genai.embed_content") as mock_embed:
            mock_embed.return_value = {"embedding": _fake_embedding()}
            with SessionLocal() as db:
                generate_embeddings(self.doc_id, db)

        assert mock_embed.call_count == 3

    def test_embed_content_uses_chunk_text_as_content(self) -> None:
        """AC-035: the content passed to embed_content is the chunk's text."""
        with patch("app.processing.genai.embed_content") as mock_embed:
            mock_embed.return_value = {"embedding": _fake_embedding()}
            with SessionLocal() as db:
                generate_embeddings(self.doc_id, db)

        contents = [call.kwargs["content"] for call in mock_embed.call_args_list]
        assert contents == ["chunk one", "chunk two", "chunk three"]

    def test_embeddings_persisted_alongside_chunk(self) -> None:
        """AC-035: embeddings are persisted on the chunk record in the DB."""
        fake_vec = _fake_embedding()
        with patch("app.processing.genai.embed_content") as mock_embed:
            mock_embed.return_value = {"embedding": fake_vec}
            with SessionLocal() as db:
                generate_embeddings(self.doc_id, db)

        with SessionLocal() as db:
            chunk = db.execute(
                select(Chunk).where(Chunk.id == self.chunk_ids[0])
            ).scalar_one()
            assert chunk.embedding == fake_vec

    def test_uses_model_name_from_settings_at_runtime(self) -> None:
        """AC-035: reads model name from get_current_settings(db) at runtime."""
        _ensure_settings(embedding_model="custom-embedding-model")

        with patch("app.processing.genai.embed_content") as mock_embed:
            mock_embed.return_value = {"embedding": _fake_embedding()}
            with SessionLocal() as db:
                generate_embeddings(self.doc_id, db)

        for call in mock_embed.call_args_list:
            assert call.kwargs["model"] == "models/custom-embedding-model"


# ---------------------------------------------------------------------------
# AC-037 — all chunks embedded → document status Ready
# ---------------------------------------------------------------------------


class TestDocumentReadyOnSuccess:
    def setup_method(self) -> None:
        _set_gemini_api_key(present=True)
        _ensure_settings()
        self.user = _create_user("us013_ready@example.com")
        self.doc_id, self.chunk_ids = _create_document_with_chunks(
            self.user.id, ["alpha", "beta"]
        )

    def teardown_method(self) -> None:
        _cleanup_documents()
        _delete_user("us013_ready@example.com")
        _set_gemini_api_key(present=False)

    def test_status_set_to_ready_after_all_embeddings(self) -> None:
        """AC-037: document status → Ready when all chunks have embeddings."""
        with patch("app.processing.genai.embed_content") as mock_embed:
            mock_embed.return_value = {"embedding": _fake_embedding()}
            with SessionLocal() as db:
                generate_embeddings(self.doc_id, db)

        with SessionLocal() as db:
            doc = db.execute(
                select(Document).where(Document.id == self.doc_id)
            ).scalar_one()
            assert doc.status == "Ready"
            assert doc.failure_reason is None

    def test_status_ready_with_no_chunks(self) -> None:
        """AC-037: a document with zero chunks is marked Ready."""
        doc_id, _ = _create_document_with_chunks(self.user.id, [])
        with SessionLocal() as db:
            generate_embeddings(doc_id, db)

        with SessionLocal() as db:
            doc = db.execute(
                select(Document).where(Document.id == doc_id)
            ).scalar_one()
            assert doc.status == "Ready"

    def test_resumable_skips_already_embedded_chunks(self) -> None:
        """AC-036/AC-037: chunks that already have embeddings are skipped,
        and the document is still marked Ready once all have embeddings."""
        with SessionLocal() as db:
            chunks = list(
                db.execute(
                    select(Chunk)
                    .where(Chunk.document_id == self.doc_id)
                    .order_by(Chunk.chunk_index)
                ).scalars()
            )
            # Pre-embed the first chunk.
            chunks[0].embedding = _fake_embedding()
            db.commit()

        with patch("app.processing.genai.embed_content") as mock_embed:
            mock_embed.return_value = {"embedding": _fake_embedding()}
            with SessionLocal() as db:
                generate_embeddings(self.doc_id, db)

        # Only the second chunk needed embedding.
        assert mock_embed.call_count == 1

        with SessionLocal() as db:
            doc = db.execute(
                select(Document).where(Document.id == self.doc_id)
            ).scalar_one()
            assert doc.status == "Ready"


# ---------------------------------------------------------------------------
# AC-036 — Gemini API error → Failed, retain data
# ---------------------------------------------------------------------------


class TestEmbeddingFailure:
    def setup_method(self) -> None:
        _set_gemini_api_key(present=True)
        _ensure_settings()
        self.user = _create_user("us013_fail@example.com")
        self.doc_id, self.chunk_ids = _create_document_with_chunks(
            self.user.id, ["first chunk", "second chunk"]
        )

    def teardown_method(self) -> None:
        _cleanup_documents()
        _delete_user("us013_fail@example.com")
        _set_gemini_api_key(present=False)

    def test_api_error_sets_status_failed(self) -> None:
        """AC-036: a Gemini API error sets the document status to Failed."""
        with patch("app.processing.genai.embed_content") as mock_embed:
            mock_embed.side_effect = RuntimeError("Quota exceeded")
            with SessionLocal() as db:
                generate_embeddings(self.doc_id, db)

        with SessionLocal() as db:
            doc = db.execute(
                select(Document).where(Document.id == self.doc_id)
            ).scalar_one()
            assert doc.status == "Failed"
            assert doc.failure_reason is not None
            assert "Quota exceeded" in doc.failure_reason

    def test_failed_reason_is_readable(self) -> None:
        """AC-036: the failure_reason is a human-readable string."""
        with patch("app.processing.genai.embed_content") as mock_embed:
            mock_embed.side_effect = Exception("503 Service Unavailable")
            with SessionLocal() as db:
                generate_embeddings(self.doc_id, db)

        with SessionLocal() as db:
            doc = db.execute(
                select(Document).where(Document.id == self.doc_id)
            ).scalar_one()
            assert isinstance(doc.failure_reason, str)
            assert len(doc.failure_reason) > 0
            assert "503" in doc.failure_reason or "Service" in doc.failure_reason

    def test_chunks_retained_on_error(self) -> None:
        """AC-036: no chunks are deleted on failure."""
        with patch("app.processing.genai.embed_content") as mock_embed:
            mock_embed.side_effect = RuntimeError("API error")
            with SessionLocal() as db:
                generate_embeddings(self.doc_id, db)

        with SessionLocal() as db:
            chunks = list(
                db.execute(
                    select(Chunk).where(Chunk.document_id == self.doc_id)
                ).scalars()
            )
            assert len(chunks) == 2

    def test_already_persisted_embeddings_retained_on_error(self) -> None:
        """AC-036: embeddings persisted before the failure are retained."""
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return {"embedding": _fake_embedding()}
            raise RuntimeError("Quota exhausted on second chunk")

        with patch("app.processing.genai.embed_content", side_effect=side_effect):
            with SessionLocal() as db:
                generate_embeddings(self.doc_id, db)

        with SessionLocal() as db:
            doc = db.execute(
                select(Document).where(Document.id == self.doc_id)
            ).scalar_one()
            assert doc.status == "Failed"

            chunks = list(
                db.execute(
                    select(Chunk)
                    .where(Chunk.document_id == self.doc_id)
                    .order_by(Chunk.chunk_index)
                ).scalars()
            )
            # First chunk's embedding was persisted and retained.
            assert chunks[0].embedding is not None
            assert len(chunks[0].embedding) == _DIM
            # Second chunk never got embedded.
            assert chunks[1].embedding is None

    def test_missing_api_key_sets_failed(self) -> None:
        """AC-036: missing GEMINI_API_KEY → Failed with readable reason."""
        _set_gemini_api_key(present=False)
        with patch("app.processing.genai.embed_content") as mock_embed:
            with SessionLocal() as db:
                generate_embeddings(self.doc_id, db)

        # The SDK was never called because the key was missing.
        assert mock_embed.call_count == 0

        with SessionLocal() as db:
            doc = db.execute(
                select(Document).where(Document.id == self.doc_id)
            ).scalar_one()
            assert doc.status == "Failed"
            assert doc.failure_reason is not None
            assert "GEMINI_API_KEY" in doc.failure_reason

    def test_missing_api_key_chunks_retained(self) -> None:
        """AC-036: chunks are retained even when the API key is missing."""
        _set_gemini_api_key(present=False)
        with SessionLocal() as db:
            generate_embeddings(self.doc_id, db)

        with SessionLocal() as db:
            chunks = list(
                db.execute(
                    select(Chunk).where(Chunk.document_id == self.doc_id)
                ).scalars()
            )
            assert len(chunks) == 2

    def test_invalid_api_key_sets_failed(self) -> None:
        """AC-036: an invalid API key (rejected by Gemini) → Failed."""
        from google.api_core.exceptions import InvalidArgument

        with patch("app.processing.genai.embed_content") as mock_embed:
            mock_embed.side_effect = InvalidArgument("API key not valid")
            with SessionLocal() as db:
                generate_embeddings(self.doc_id, db)

        with SessionLocal() as db:
            doc = db.execute(
                select(Document).where(Document.id == self.doc_id)
            ).scalar_one()
            assert doc.status == "Failed"
            assert "API key not valid" in (doc.failure_reason or "")

    def test_wrong_dimension_sets_failed(self) -> None:
        """AC-036: a non-768-dimensional embedding → Failed."""
        with patch("app.processing.genai.embed_content") as mock_embed:
            mock_embed.return_value = {"embedding": [0.1] * 256}
            with SessionLocal() as db:
                generate_embeddings(self.doc_id, db)

        with SessionLocal() as db:
            doc = db.execute(
                select(Document).where(Document.id == self.doc_id)
            ).scalar_one()
            assert doc.status == "Failed"
            assert doc.failure_reason is not None


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def setup_method(self) -> None:
        _set_gemini_api_key(present=True)
        _ensure_settings()
        self.user = _create_user("us013_edge@example.com")

    def teardown_method(self) -> None:
        _cleanup_documents()
        _delete_user("us013_edge@example.com")
        _set_gemini_api_key(present=False)

    def test_nonexistent_document_is_noop(self) -> None:
        """Calling with a UUID that has no document row does not raise."""
        fake_id = uuid_mod.uuid4()
        with patch("app.processing.genai.embed_content") as mock_embed:
            with SessionLocal() as db:
                generate_embeddings(fake_id, db)
        assert mock_embed.call_count == 0

    def test_single_chunk_document(self) -> None:
        """A document with one chunk is embedded and marked Ready."""
        doc_id, _ = _create_document_with_chunks(self.user.id, ["only chunk"])
        with patch("app.processing.genai.embed_content") as mock_embed:
            mock_embed.return_value = {"embedding": _fake_embedding()}
            with SessionLocal() as db:
                generate_embeddings(doc_id, db)

        with SessionLocal() as db:
            doc = db.execute(
                select(Document).where(Document.id == doc_id)
            ).scalar_one()
            assert doc.status == "Ready"
        assert mock_embed.call_count == 1

    def test_model_name_already_prefixed(self) -> None:
        """A model name already starting with 'models/' is not double-prefixed."""
        _ensure_settings(embedding_model="models/text-embedding-004")
        doc_id, _ = _create_document_with_chunks(self.user.id, ["prefixed"])
        with patch("app.processing.genai.embed_content") as mock_embed:
            mock_embed.return_value = {"embedding": _fake_embedding()}
            with SessionLocal() as db:
                generate_embeddings(doc_id, db)

        for call in mock_embed.call_args_list:
            assert call.kwargs["model"] == "models/text-embedding-004"