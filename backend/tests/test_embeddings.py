"""Integration tests for Gemini embedding generation (US-013-2).

Covers:
  AC-035 — a 768-dimensional embedding vector is generated via the Gemini API
           and persisted alongside each chunk record.
  AC-036 — when the Gemini API returns an error or quota failure, the document
           status is set to Failed with a readable reason, the uploaded file
           and all already-persisted chunks/embeddings are retained, and no
           data is deleted.
  AC-037 — when embeddings have been generated for all chunks and persisted,
           the document status is set to Ready.

Follows patterns from test_documents.py and test_auth_login.py: direct DB
inserts for fixtures, setup/teardown cleanup, mock the google-generativeai
SDK so no real API calls are made, call ``generate_embeddings`` directly
(no Redis / rq required).
"""

from __future__ import annotations

import os
import uuid as uuid_mod
from pathlib import Path
from unittest.mock import patch

import bcrypt
from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.models import Chunk, Document, Settings, User
from app.processing import generate_embeddings

# Ensure all tables exist on the test database (conftest.py sets DATABASE_URL
# and removes stale DB files before this module is imported).
Base.metadata.create_all(bind=engine)

_DIM = 768


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hash(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _create_user(email: str, password: str = "pw-123", role: str = "Administrator") -> User:
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


def _create_document_with_chunks(
    user_id: int,
    chunk_texts: list[str],
    status: str = "Processing",
    file_path: str = "/tmp/us013_test_file.txt",
) -> tuple[uuid_mod.UUID, list[uuid_mod.UUID]]:
    """Insert a Document with the given chunk texts and return (doc_id, chunk_ids)."""
    with SessionLocal() as db:
        doc = Document(
            filename="test.txt",
            file_type="TXT",
            file_size=100,
            file_path=file_path,
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
    """Delete all Document rows (and their chunks via cascade) from the test DB."""
    with SessionLocal() as db:
        docs = db.execute(select(Document)).scalars().all()
        for d in docs:
            db.delete(d)
        db.commit()


def _fake_embedding(dim: int = _DIM) -> list[float]:
    """Return a deterministic fake embedding vector of the given dimension."""
    return [float(i) for i in range(dim)]


def _set_gemini_api_key(present: bool = True) -> None:
    """Set or remove the GEMINI_API_KEY env var."""
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


# ---------------------------------------------------------------------------
# AC-035 — 768-dimensional embedding generated and persisted per chunk
# ---------------------------------------------------------------------------


class TestEmbeddingSuccess:
    """AC-035: each chunk gets a 768-dim embedding via the Gemini API,
    persisted alongside the chunk record."""

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
        """Each chunk receives exactly a 768-dimensional embedding."""
        with patch("app.processing.genai.embed_content") as mock_embed:
            mock_embed.return_value = {"embedding": _fake_embedding()}

            with SessionLocal() as db:
                generate_embeddings(self.doc_id, db)

        chunks = _get_chunks(self.doc_id)
        assert len(chunks) == 3
        for chunk in chunks:
            assert chunk.embedding is not None
            assert len(chunk.embedding) == _DIM

    def test_embeddings_persisted_alongside_chunk_records(self) -> None:
        """The embedding is stored on the chunk row in the database."""
        fake_vec = _fake_embedding()
        with patch("app.processing.genai.embed_content") as mock_embed:
            mock_embed.return_value = {"embedding": fake_vec}

            with SessionLocal() as db:
                generate_embeddings(self.doc_id, db)

        with SessionLocal() as db:
            chunk = db.execute(select(Chunk).where(Chunk.id == self.chunk_ids[0])).scalar_one()
            assert chunk.embedding is not None
            assert len(chunk.embedding) == _DIM

    def test_embed_content_called_once_per_chunk(self) -> None:
        """genai.embed_content is called exactly once per chunk."""
        with patch("app.processing.genai.embed_content") as mock_embed:
            mock_embed.return_value = {"embedding": _fake_embedding()}

            with SessionLocal() as db:
                generate_embeddings(self.doc_id, db)

        assert mock_embed.call_count == 3

    def test_embed_content_uses_chunk_text_as_content(self) -> None:
        """The content passed to embed_content is the chunk's text."""
        with patch("app.processing.genai.embed_content") as mock_embed:
            mock_embed.return_value = {"embedding": _fake_embedding()}

            with SessionLocal() as db:
                generate_embeddings(self.doc_id, db)

        contents = [call.kwargs["content"] for call in mock_embed.call_args_list]
        assert contents == ["chunk one", "chunk two", "chunk three"]

    def test_embed_content_uses_model_from_settings(self) -> None:
        """The model name passed to embed_content comes from Settings."""
        _ensure_settings(embedding_model="text-embedding-004")

        with patch("app.processing.genai.embed_content") as mock_embed:
            mock_embed.return_value = {"embedding": _fake_embedding()}

            with SessionLocal() as db:
                generate_embeddings(self.doc_id, db)

        for call in mock_embed.call_args_list:
            assert call.kwargs["model"] == "models/text-embedding-004"
            assert call.kwargs["output_dimensionality"] == _DIM

    def test_uses_model_name_from_settings_at_runtime(self) -> None:
        """The model name is read from get_current_settings(db) at call time."""
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
    """AC-037: when all chunks have embeddings, document status → Ready."""

    def setup_method(self) -> None:
        _set_gemini_api_key(present=True)
        _ensure_settings()
        self.user = _create_user("us013_ready@example.com")
        self.doc_id, self.chunk_ids = _create_document_with_chunks(self.user.id, ["alpha", "beta"])

    def teardown_method(self) -> None:
        _cleanup_documents()
        _delete_user("us013_ready@example.com")
        _set_gemini_api_key(present=False)

    def test_status_set_to_ready_after_all_embeddings(self) -> None:
        """Document status transitions to Ready when all chunks are embedded."""
        with patch("app.processing.genai.embed_content") as mock_embed:
            mock_embed.return_value = {"embedding": _fake_embedding()}

            with SessionLocal() as db:
                generate_embeddings(self.doc_id, db)

        doc = _get_document(self.doc_id)
        assert doc.status == "Ready"
        assert doc.failure_reason is None

    def test_status_ready_with_no_chunks(self) -> None:
        """A document with zero chunks is marked Ready (nothing to embed)."""
        doc_id, _ = _create_document_with_chunks(self.user.id, [])

        with SessionLocal() as db:
            generate_embeddings(doc_id, db)

        doc = _get_document(doc_id)
        assert doc.status == "Ready"

    def test_single_chunk_document_marked_ready(self) -> None:
        """A document with one chunk is embedded and marked Ready."""
        doc_id, _ = _create_document_with_chunks(self.user.id, ["only chunk"])

        with patch("app.processing.genai.embed_content") as mock_embed:
            mock_embed.return_value = {"embedding": _fake_embedding()}

            with SessionLocal() as db:
                generate_embeddings(doc_id, db)

        doc = _get_document(doc_id)
        assert doc.status == "Ready"
        assert mock_embed.call_count == 1

    def test_resumable_skips_already_embedded_chunks(self) -> None:
        """Chunks that already have embeddings are skipped; the document is
        still marked Ready once all have embeddings."""
        with SessionLocal() as db:
            chunks = list(
                db.execute(
                    select(Chunk)
                    .where(Chunk.document_id == self.doc_id)
                    .order_by(Chunk.chunk_index)
                ).scalars()
            )
            chunks[0].embedding = _fake_embedding()
            db.commit()

        with patch("app.processing.genai.embed_content") as mock_embed:
            mock_embed.return_value = {"embedding": _fake_embedding()}

            with SessionLocal() as db:
                generate_embeddings(self.doc_id, db)

        assert mock_embed.call_count == 1

        doc = _get_document(self.doc_id)
        assert doc.status == "Ready"


# ---------------------------------------------------------------------------
# AC-036 — Gemini API error → Failed status, readable reason, data retained
# ---------------------------------------------------------------------------


class TestEmbeddingFailure:
    """AC-036: on Gemini API error, document status → Failed with a readable
    reason; chunks, already-persisted embeddings, and the uploaded file are
    retained — nothing is deleted."""

    def setup_method(self) -> None:
        _set_gemini_api_key(present=True)
        _ensure_settings()
        self.user = _create_user("us013_fail@example.com")
        # Create a real temporary file so we can verify it survives failure.
        self.tmp_file = Path("/tmp") / "us013_fail_test_file.txt"
        self.tmp_file.write_bytes(b"test content for retention")
        self.doc_id, self.chunk_ids = _create_document_with_chunks(
            self.user.id,
            ["first chunk", "second chunk"],
            file_path=str(self.tmp_file),
        )

    def teardown_method(self) -> None:
        _cleanup_documents()
        _delete_user("us013_fail@example.com")
        if self.tmp_file.exists():
            self.tmp_file.unlink()
        _set_gemini_api_key(present=False)

    def test_api_error_sets_status_failed(self) -> None:
        """A Gemini API error sets the document status to Failed."""
        with patch("app.processing.genai.embed_content") as mock_embed:
            mock_embed.side_effect = RuntimeError("Quota exceeded")

            with SessionLocal() as db:
                generate_embeddings(self.doc_id, db)

        doc = _get_document(self.doc_id)
        assert doc.status == "Failed"

    def test_failed_reason_is_readable(self) -> None:
        """The failure_reason is a non-empty, human-readable string."""
        with patch("app.processing.genai.embed_content") as mock_embed:
            mock_embed.side_effect = Exception("503 Service Unavailable")

            with SessionLocal() as db:
                generate_embeddings(self.doc_id, db)

        doc = _get_document(self.doc_id)
        assert doc.failure_reason is not None
        assert isinstance(doc.failure_reason, str)
        assert len(doc.failure_reason) > 0
        assert "503" in doc.failure_reason or "Service" in doc.failure_reason

    def test_failed_reason_includes_error_detail(self) -> None:
        """The failure_reason contains the original error message."""
        with patch("app.processing.genai.embed_content") as mock_embed:
            mock_embed.side_effect = RuntimeError("Quota exceeded")

            with SessionLocal() as db:
                generate_embeddings(self.doc_id, db)

        doc = _get_document(self.doc_id)
        assert doc.failure_reason is not None
        assert "Quota exceeded" in doc.failure_reason

    def test_chunks_retained_on_error(self) -> None:
        """No chunks are deleted when the Gemini API fails."""
        with patch("app.processing.genai.embed_content") as mock_embed:
            mock_embed.side_effect = RuntimeError("API error")

            with SessionLocal() as db:
                generate_embeddings(self.doc_id, db)

        chunks = _get_chunks(self.doc_id)
        assert len(chunks) == 2

    def test_uploaded_file_retained_on_error(self) -> None:
        """The uploaded file must still exist after a failure."""
        assert self.tmp_file.exists()

        with patch("app.processing.genai.embed_content") as mock_embed:
            mock_embed.side_effect = RuntimeError("API error")

            with SessionLocal() as db:
                generate_embeddings(self.doc_id, db)

        assert self.tmp_file.exists()
        assert self.tmp_file.read_bytes() == b"test content for retention"

    def test_already_persisted_embeddings_retained_on_error(self) -> None:
        """Embeddings persisted before the failure are retained (not deleted)."""
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return {"embedding": _fake_embedding()}
            raise RuntimeError("Quota exhausted on second chunk")

        with patch("app.processing.genai.embed_content", side_effect=side_effect):
            with SessionLocal() as db:
                generate_embeddings(self.doc_id, db)

        doc = _get_document(self.doc_id)
        assert doc.status == "Failed"

        chunks = _get_chunks(self.doc_id)
        assert len(chunks) == 2
        # First chunk's embedding was persisted and retained.
        assert chunks[0].embedding is not None
        assert len(chunks[0].embedding) == _DIM
        # Second chunk never got embedded.
        assert chunks[1].embedding is None

    def test_no_data_deleted_on_failure(self) -> None:
        """Comprehensive: document, chunks, file, and partial embeddings all
        survive a failure."""
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return {"embedding": _fake_embedding()}
            raise RuntimeError("Network timeout")

        with patch("app.processing.genai.embed_content", side_effect=side_effect):
            with SessionLocal() as db:
                generate_embeddings(self.doc_id, db)

        # Document still exists.
        doc = _get_document(self.doc_id)
        assert doc.status == "Failed"

        # Both chunks still exist.
        chunks = _get_chunks(self.doc_id)
        assert len(chunks) == 2

        # File still exists.
        assert self.tmp_file.exists()

        # First chunk's embedding was retained.
        assert chunks[0].embedding is not None

    def test_missing_api_key_sets_failed(self) -> None:
        """Missing GEMINI_API_KEY → Failed with a readable reason."""
        _set_gemini_api_key(present=False)

        with patch("app.processing.genai.embed_content") as mock_embed:
            with SessionLocal() as db:
                generate_embeddings(self.doc_id, db)

        assert mock_embed.call_count == 0

        doc = _get_document(self.doc_id)
        assert doc.status == "Failed"
        assert doc.failure_reason is not None
        assert "GEMINI_API_KEY" in doc.failure_reason

    def test_missing_api_key_chunks_retained(self) -> None:
        """Chunks are retained even when the API key is missing."""
        _set_gemini_api_key(present=False)

        with SessionLocal() as db:
            generate_embeddings(self.doc_id, db)

        chunks = _get_chunks(self.doc_id)
        assert len(chunks) == 2

    def test_wrong_dimension_sets_failed(self) -> None:
        """A non-768-dimensional response → Failed."""
        with patch("app.processing.genai.embed_content") as mock_embed:
            mock_embed.return_value = {"embedding": [0.1] * 256}

            with SessionLocal() as db:
                generate_embeddings(self.doc_id, db)

        doc = _get_document(self.doc_id)
        assert doc.status == "Failed"
        assert doc.failure_reason is not None

    def test_wrong_dimension_chunks_retained(self) -> None:
        """Chunks are retained when the embedding dimension is wrong."""
        with patch("app.processing.genai.embed_content") as mock_embed:
            mock_embed.return_value = {"embedding": [0.1] * 256}

            with SessionLocal() as db:
                generate_embeddings(self.doc_id, db)

        chunks = _get_chunks(self.doc_id)
        assert len(chunks) == 2


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

    def test_empty_chunk_text_still_embedded(self) -> None:
        """A chunk with empty text still gets an embedding."""
        doc_id, _ = _create_document_with_chunks(self.user.id, [""])

        with patch("app.processing.genai.embed_content") as mock_embed:
            mock_embed.return_value = {"embedding": _fake_embedding()}

            with SessionLocal() as db:
                generate_embeddings(doc_id, db)

        chunks = _get_chunks(doc_id)
        assert len(chunks) == 1
        assert chunks[0].embedding is not None
        assert len(chunks[0].embedding) == _DIM

        doc = _get_document(doc_id)
        assert doc.status == "Ready"
