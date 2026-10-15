"""Acceptance tests for US-021: Store Embeddings in Database.

Covers:
  AC-059 — Given an embedding has been generated for a chunk via the Gemini
           API, when the embedding is persisted, then the 768-dimensional
           vector is stored in the database associated with its chunk ID and
           document ID.
  AC-060 — Given the application restarts, when the vector store is accessed,
           then all previously stored embeddings are available from the
           database without regeneration.

These are backend integration tests that exercise the real database layer
(SQLAlchemy + pgvector Vector(768) column) using the same SQLite test
database configured by ``conftest.py``.  The Gemini API is mocked so no
network calls are made.

AC-060 ("restart") is simulated by disposing the current SQLAlchemy engine
and creating a brand-new engine + session factory bound to the same
database file.  This mirrors what happens when the process restarts: the
in-memory ORM identity map and connection pool are gone, and the only way
to retrieve embeddings is to read them back from the persistent store.
"""

from __future__ import annotations

import os
import uuid as uuid_mod
from unittest.mock import patch

import bcrypt
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base, SessionLocal, engine
from app.models import Chunk, Document, Settings, User
from app.processing import generate_embeddings

# Ensure all tables exist on the test database (conftest.py sets
# DATABASE_URL and removes stale DB files before this module is imported).
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
    with SessionLocal() as db:
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is not None:
            db.delete(user)
        db.commit()


def _create_document_with_chunks(
    user_id: int,
    chunk_texts: list[str],
    status: str = "Processing",
    file_path: str = "/tmp/us021_test_file.txt",
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
    with SessionLocal() as db:
        docs = db.execute(select(Document)).scalars().all()
        for d in docs:
            db.delete(d)
        db.commit()


def _fake_embedding(dim: int = _DIM, seed: int = 0) -> list[float]:
    """Return a deterministic fake embedding vector of the given dimension.

    The ``seed`` parameter produces distinct vectors per chunk so tests can
    verify that each chunk's stored embedding matches the value the Gemini
    mock returned for that specific chunk.
    """
    return [float(seed * dim + i) for i in range(dim)]


def _set_gemini_api_key(present: bool = True) -> None:
    if present:
        os.environ["GEMINI_API_KEY"] = "test-api-key"
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


def _new_engine_and_session():
    """Create a fresh engine + session factory bound to the same DB URL.

    Used to simulate an application restart: the old engine's connection
    pool and ORM identity map are gone, so the only way to retrieve data is
    to read it back from the persistent store.
    """
    from app.database import DATABASE_URL

    new_engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
        future=True,
    )
    new_session = sessionmaker(bind=new_engine, autoflush=False, expire_on_commit=False)
    return new_engine, new_session


# ---------------------------------------------------------------------------
# AC-059 — 768-dim vector stored in DB associated with chunk ID + document ID
# ---------------------------------------------------------------------------


class TestEmbeddingPersistedToDatabase:
    """AC-059: the 768-dimensional vector is stored in the database
    associated with its chunk ID and document ID."""

    def setup_method(self) -> None:
        _set_gemini_api_key(present=True)
        _ensure_settings()
        self.user = _create_user("us021_persist@example.com")
        self.doc_id, self.chunk_ids = _create_document_with_chunks(
            self.user.id, ["alpha chunk", "beta chunk", "gamma chunk"]
        )

    def teardown_method(self) -> None:
        _cleanup_documents()
        _delete_user("us021_persist@example.com")
        _set_gemini_api_key(present=False)

    def test_embedding_stored_with_correct_chunk_id(self) -> None:
        """Each stored embedding is retrievable by its chunk ID."""
        embeddings_by_chunk = {
            self.chunk_ids[0]: _fake_embedding(seed=1),
            self.chunk_ids[1]: _fake_embedding(seed=2),
            self.chunk_ids[2]: _fake_embedding(seed=3),
        }

        def fake_embed(*args, **kwargs):
            content = kwargs["content"]
            seed_map = {"alpha chunk": 1, "beta chunk": 2, "gamma chunk": 3}
            return {"embedding": _fake_embedding(seed=seed_map[content])}

        with patch("app.processing.genai.embed_content", side_effect=fake_embed):
            with SessionLocal() as db:
                generate_embeddings(self.doc_id, db)

        with SessionLocal() as db:
            for chunk_id, expected_vec in embeddings_by_chunk.items():
                chunk = db.execute(select(Chunk).where(Chunk.id == chunk_id)).scalar_one()
                assert chunk.embedding is not None
                assert len(chunk.embedding) == _DIM
                assert list(chunk.embedding) == expected_vec

    def test_embedding_stored_with_correct_document_id(self) -> None:
        """The chunk holding the embedding is associated with the correct
        document ID."""
        with patch("app.processing.genai.embed_content") as mock_embed:
            mock_embed.return_value = {"embedding": _fake_embedding()}

            with SessionLocal() as db:
                generate_embeddings(self.doc_id, db)

        with SessionLocal() as db:
            chunks = list(
                db.execute(select(Chunk).where(Chunk.document_id == self.doc_id)).scalars()
            )
            assert len(chunks) == 3
            for chunk in chunks:
                assert chunk.document_id == self.doc_id
                assert chunk.embedding is not None
                assert len(chunk.embedding) == _DIM

    def test_embedding_is_exactly_768_dimensions(self) -> None:
        """The stored vector is exactly 768-dimensional."""
        with patch("app.processing.genai.embed_content") as mock_embed:
            mock_embed.return_value = {"embedding": _fake_embedding()}

            with SessionLocal() as db:
                generate_embeddings(self.doc_id, db)

        chunks = _get_chunks(self.doc_id)
        for chunk in chunks:
            assert chunk.embedding is not None
            assert len(chunk.embedding) == _DIM

    def test_embedding_survives_commit_and_new_session(self) -> None:
        """The embedding is flushed to the database — not just held in the
        ORM session — so a fresh session reads it back."""
        with patch("app.processing.genai.embed_content") as mock_embed:
            mock_embed.return_value = {"embedding": _fake_embedding(seed=7)}

            with SessionLocal() as db:
                generate_embeddings(self.doc_id, db)

        fresh = SessionLocal()
        try:
            chunk = fresh.execute(
                select(Chunk).where(Chunk.id == self.chunk_ids[0])
            ).scalar_one()
            assert chunk.embedding is not None
            assert len(chunk.embedding) == _DIM
            assert list(chunk.embedding) == _fake_embedding(seed=7)
        finally:
            fresh.close()

    def test_multiple_documents_embeddings_stored_separately(self) -> None:
        """Embeddings from two different documents are stored independently,
        each associated with the correct document and chunk IDs."""
        doc_id_2, _chunk_ids_2 = _create_document_with_chunks(
            self.user.id, ["second doc chunk"]
        )

        try:
            with patch("app.processing.genai.embed_content") as mock_embed:
                mock_embed.return_value = {"embedding": _fake_embedding()}

                with SessionLocal() as db:
                    generate_embeddings(self.doc_id, db)
                    generate_embeddings(doc_id_2, db)

            with SessionLocal() as db:
                chunks_1 = list(
                    db.execute(
                        select(Chunk).where(Chunk.document_id == self.doc_id)
                    ).scalars()
                )
                assert len(chunks_1) == 3
                for c in chunks_1:
                    assert c.embedding is not None
                    assert len(c.embedding) == _DIM
                    assert c.document_id == self.doc_id

                chunks_2 = list(
                    db.execute(
                        select(Chunk).where(Chunk.document_id == doc_id_2)
                    ).scalars()
                )
                assert len(chunks_2) == 1
                for c in chunks_2:
                    assert c.embedding is not None
                    assert len(c.embedding) == _DIM
                    assert c.document_id == doc_id_2
        finally:
            with SessionLocal() as db:
                doc = db.execute(
                    select(Document).where(Document.id == doc_id_2)
                ).scalar_one_or_none()
                if doc:
                    db.delete(doc)
                db.commit()


# ---------------------------------------------------------------------------
# AC-060 — embeddings available after restart without regeneration
# ---------------------------------------------------------------------------


class TestEmbeddingsAvailableAfterRestart:
    """AC-060: after the application restarts, all previously stored
    embeddings are available from the database without regeneration.

    "Restart" is simulated by disposing the current SQLAlchemy engine and
    creating a brand-new engine + session factory bound to the same
    database file.  This mirrors a process restart: the in-memory ORM
    identity map and connection pool are gone, and the only way to retrieve
    embeddings is to read them back from the persistent store.
    """

    def setup_method(self) -> None:
        _set_gemini_api_key(present=True)
        _ensure_settings()
        self.user = _create_user("us021_restart@example.com")
        self.doc_id, self.chunk_ids = _create_document_with_chunks(
            self.user.id, ["restart chunk one", "restart chunk two", "restart chunk three"]
        )

    def teardown_method(self) -> None:
        _cleanup_documents()
        _delete_user("us021_restart@example.com")
        _set_gemini_api_key(present=False)

    def _generate_embeddings(self) -> None:
        """Generate embeddings for the test document using a mocked Gemini API."""
        with patch("app.processing.genai.embed_content") as mock_embed:
            mock_embed.return_value = {"embedding": _fake_embedding()}

            with SessionLocal() as db:
                generate_embeddings(self.doc_id, db)

    def test_embeddings_available_after_engine_recreation(self) -> None:
        """After disposing the engine and creating a new one, all embeddings
        are readable from the database."""
        self._generate_embeddings()

        engine.dispose()
        new_engine, new_session = _new_engine_and_session()

        try:
            with new_session() as db:
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
        finally:
            new_engine.dispose()

    def test_no_regeneration_needed_after_restart(self) -> None:
        """After restart, embeddings are retrieved without any Gemini API
        calls — no regeneration occurs."""
        self._generate_embeddings()

        engine.dispose()
        new_engine, new_session = _new_engine_and_session()

        try:
            with patch("app.processing.genai.embed_content") as mock_embed:
                with new_session() as db:
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

                assert mock_embed.call_count == 0
        finally:
            new_engine.dispose()

    def test_all_embeddings_available_after_restart(self) -> None:
        """Every previously stored embedding is available after restart —
        none are missing."""
        seed_map = {
            "restart chunk one": 10,
            "restart chunk two": 20,
            "restart chunk three": 30,
        }

        def fake_embed(*args, **kwargs):
            return {"embedding": _fake_embedding(seed=seed_map[kwargs["content"]])}

        with patch("app.processing.genai.embed_content", side_effect=fake_embed):
            with SessionLocal() as db:
                generate_embeddings(self.doc_id, db)

        engine.dispose()
        new_engine, new_session = _new_engine_and_session()

        try:
            with new_session() as db:
                chunks = list(
                    db.execute(
                        select(Chunk)
                        .where(Chunk.document_id == self.doc_id)
                        .order_by(Chunk.chunk_index)
                    ).scalars()
                )
                assert len(chunks) == 3

                expected_seeds = [10, 20, 30]
                for chunk, seed in zip(chunks, expected_seeds):
                    assert chunk.embedding is not None
                    assert len(chunk.embedding) == _DIM
                    assert list(chunk.embedding) == _fake_embedding(seed=seed)
        finally:
            new_engine.dispose()

    def test_document_status_remains_ready_after_restart(self) -> None:
        """After restart, the document's Ready status is still persisted."""
        self._generate_embeddings()

        doc = _get_document(self.doc_id)
        assert doc.status == "Ready"

        engine.dispose()
        new_engine, new_session = _new_engine_and_session()

        try:
            with new_session() as db:
                doc = db.execute(
                    select(Document).where(Document.id == self.doc_id)
                ).scalar_one()
                assert doc.status == "Ready"
                assert doc.failure_reason is None
        finally:
            new_engine.dispose()