"""Integration tests for POST /documents and GET /documents (US-009-3).

Covers:
  AC-021 — admin uploads valid PDF/DOCX/TXT/MD ≤ 25 MB; file saved to
           backend/uploads, Document DB record created with status='Processing'.
  AC-022 — upload > 25 MB → 422 with size-limit message, no file or DB record.
  AC-023 — upload unsupported file type → 422 with supported-types message,
           no file or DB record.
  AC-024 — regular (non-admin) user uploads → 403 Forbidden, no file stored.
  AC-042 — GET /documents returns list from DB with filename, type, size,
           created_at, status.
  AC-045 — GET /documents does not include password hashes or sensitive fields.
  AC-043 — documents persist across simulated restart (data read from DB after
           new SessionLocal).
  AC-044 — startup does not truncate or delete existing document records.
  AC-052 — admin DELETE /documents/{id} deletes file, document, chunks,
           embeddings, and citations.
  AC-053 — after deletion, GET /documents does not include the deleted document.
  AC-054 — after deletion, no chunks or citations remain for that document_id.
  AC-055 — regular (non-admin) user DELETE → 403, no data removed.

Follows patterns from test_auth_login.py and test_users.py: TestClient, direct
DB inserts for fixtures, login to obtain session cookies, try/finally cleanup.

Size-limit tests patch ``MAX_FILE_SIZE`` to a small value rather than
allocating a 25 MB buffer, per the test constraints.
"""

from __future__ import annotations

import uuid as uuid_mod
from pathlib import Path
from unittest.mock import patch

import bcrypt
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import (
    Citation,
    Chunk,
    Conversation,
    Document,
    Message,
    User,
)
from app.routers.documents import UPLOAD_DIR
from app.seed import seed_admin

client = TestClient(app)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hash(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _create_user(email: str, password: str, role: str = "Regular User") -> User:
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


def _login(email: str, password: str) -> str:
    """Log in and return the session_id cookie value."""
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.cookies.get("session_id") or ""


def _logout(session_id: str) -> None:
    client.post("/auth/logout", cookies={"session_id": session_id})


def _cleanup_documents() -> None:
    """Delete all Document rows and remove their files from uploads."""
    with SessionLocal() as db:
        # Delete citations first (FK to documents and chunks)
        citations = db.execute(select(Citation)).scalars().all()
        for c in citations:
            db.delete(c)
        # Delete messages and conversations to avoid orphaned FK references
        messages = db.execute(select(Message)).scalars().all()
        for m in messages:
            db.delete(m)
        conversations = db.execute(select(Conversation)).scalars().all()
        for conv in conversations:
            db.delete(conv)
        # Delete chunks
        chunks = db.execute(select(Chunk)).scalars().all()
        for ch in chunks:
            db.delete(ch)
        # Delete documents
        docs = db.execute(select(Document)).scalars().all()
        for d in docs:
            p = Path(d.file_path)
            if p.exists():
                p.unlink()
            db.delete(d)
        db.commit()


def _document_count() -> int:
    with SessionLocal() as db:
        return len(db.execute(select(Document)).scalars().all())


def _make_file(content: bytes, filename: str) -> tuple[str, bytes]:
    """Return (filename, content) for the ``files`` param of TestClient."""
    return (filename, content)


def _to_uuid(value: str) -> uuid_mod.UUID:
    """Convert a JSON-serialised UUID string to ``uuid.UUID``."""
    return uuid_mod.UUID(str(value))


def _files_before() -> set[Path]:
    """Snapshot of files currently in the uploads directory."""
    return set(UPLOAD_DIR.glob("*"))


def _create_chunks_and_citations(doc_id: uuid_mod.UUID, user_id: int) -> None:
    """Insert chunks, a conversation, message, and citations for a document.

    This sets up the related records that DELETE must cascade-clean so the
    tests can verify AC-052 and AC-054.
    """
    with SessionLocal() as db:
        # Two chunks with embeddings for the document
        chunk1 = Chunk(
            document_id=doc_id,
            chunk_text="chunk one text",
            chunk_index=0,
            page_section="page 1",
            embedding=[0.1] * 768,
        )
        chunk2 = Chunk(
            document_id=doc_id,
            chunk_text="chunk two text",
            chunk_index=1,
            page_section="page 2",
            embedding=[0.2] * 768,
        )
        db.add(chunk1)
        db.add(chunk2)
        db.flush()

        # A conversation + message so we can attach citations
        conversation = Conversation(user_id=user_id, title="Test conversation")
        db.add(conversation)
        db.flush()

        message = Message(
            conversation_id=conversation.id,
            role="assistant",
            content="Answer based on the document",
        )
        db.add(message)
        db.flush()

        # Citations linking the message to the document's chunks
        citation1 = Citation(
            message_id=message.id,
            document_id=doc_id,
            chunk_id=chunk1.id,
            filename="delete-me.txt",
            page_section="page 1",
        )
        citation2 = Citation(
            message_id=message.id,
            document_id=doc_id,
            chunk_id=chunk2.id,
            filename="delete-me.txt",
            page_section="page 2",
        )
        db.add(citation1)
        db.add(citation2)
        db.commit()


# ---------------------------------------------------------------------------
# AC-021 — admin uploads a supported file ≤ 25 MB
# ---------------------------------------------------------------------------


class TestUploadSuccess:
    def setup_method(self) -> None:
        self.admin_email = "us009_admin_upload@example.com"
        self.admin_pw = "admin-pw-123"
        _create_user(self.admin_email, self.admin_pw, role="Administrator")
        self.session_id = _login(self.admin_email, self.admin_pw)
        _cleanup_documents()

    def teardown_method(self) -> None:
        _logout(self.session_id)
        _cleanup_documents()
        _delete_user(self.admin_email)

    def test_admin_uploads_pdf(self) -> None:
        content = b"%PDF-1.4 test"
        resp = client.post(
            "/documents",
            files={"file": _make_file(content, "report.pdf")},
            cookies={"session_id": self.session_id},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["filename"] == "report.pdf"
        assert body["file_type"] == "PDF"
        assert body["file_size"] == len(content)
        assert body["status"] == "Processing"
        assert "id" in body
        assert "created_at" in body

    def test_admin_uploads_docx(self) -> None:
        content = b"PK\x03\x04 fake docx"
        resp = client.post(
            "/documents",
            files={"file": _make_file(content, "doc.docx")},
            cookies={"session_id": self.session_id},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["filename"] == "doc.docx"
        assert body["file_type"] == "DOCX"
        assert body["file_size"] == len(content)
        assert body["status"] == "Processing"

    def test_admin_uploads_txt(self) -> None:
        content = b"Hello, world!"
        resp = client.post(
            "/documents",
            files={"file": _make_file(content, "test.txt")},
            cookies={"session_id": self.session_id},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["filename"] == "test.txt"
        assert body["file_type"] == "TXT"
        assert body["file_size"] == len(content)
        assert body["status"] == "Processing"

    def test_admin_uploads_md(self) -> None:
        content = b"# Markdown heading"
        resp = client.post(
            "/documents",
            files={"file": _make_file(content, "readme.md")},
            cookies={"session_id": self.session_id},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["filename"] == "readme.md"
        assert body["file_type"] == "MD"
        assert body["file_size"] == len(content)
        assert body["status"] == "Processing"

    def test_file_saved_to_uploads_directory(self) -> None:
        """The uploaded file must be persisted in backend/uploads."""
        content = b"persisted content"
        resp = client.post(
            "/documents",
            files={"file": _make_file(content, "persist.txt")},
            cookies={"session_id": self.session_id},
        )
        assert resp.status_code == 200
        doc_id = _to_uuid(resp.json()["id"])

        with SessionLocal() as db:
            doc = db.execute(select(Document).where(Document.id == doc_id)).scalar_one()
            saved = Path(doc.file_path)
            assert saved.exists()
            assert saved.parent == UPLOAD_DIR.resolve()
            assert saved.read_bytes() == content

    def test_db_record_created_with_processing_status(self) -> None:
        """A Document row must exist with status='Processing'."""
        content = b"db record test"
        resp = client.post(
            "/documents",
            files={"file": _make_file(content, "dbcheck.txt")},
            cookies={"session_id": self.session_id},
        )
        assert resp.status_code == 200
        doc_id = _to_uuid(resp.json()["id"])

        with SessionLocal() as db:
            doc = db.execute(select(Document).where(Document.id == doc_id)).scalar_one()
            assert doc.status == "Processing"
            assert doc.filename == "dbcheck.txt"
            assert doc.file_type == "TXT"
            assert doc.file_size == len(content)
            assert doc.file_path  # non-empty path

    def test_upload_at_exact_limit_boundary(self) -> None:
        """A file exactly at the size limit must be accepted."""
        # Patch to a small limit so we don't allocate 25 MB.
        with patch("app.routers.documents.MAX_FILE_SIZE", 100):
            content = b"\x00" * 100
            resp = client.post(
                "/documents",
                files={"file": _make_file(content, "exact.txt")},
                cookies={"session_id": self.session_id},
            )
        assert resp.status_code == 200, resp.text
        assert resp.json()["file_size"] == 100


# ---------------------------------------------------------------------------
# AC-022 — upload exceeds size limit → 422, no file or DB record
# ---------------------------------------------------------------------------


class TestUploadSizeLimit:
    def setup_method(self) -> None:
        self.admin_email = "us009_admin_size@example.com"
        self.admin_pw = "admin-pw-123"
        _create_user(self.admin_email, self.admin_pw, role="Administrator")
        self.session_id = _login(self.admin_email, self.admin_pw)
        _cleanup_documents()

    def teardown_method(self) -> None:
        _logout(self.session_id)
        _cleanup_documents()
        _delete_user(self.admin_email)

    def test_oversized_file_rejected_with_422(self) -> None:
        """Patch MAX_FILE_SIZE to a small value and upload just over it."""
        with patch("app.routers.documents.MAX_FILE_SIZE", 100):
            content = b"\x00" * 101
            resp = client.post(
                "/documents",
                files={"file": _make_file(content, "big.txt")},
                cookies={"session_id": self.session_id},
            )
        assert resp.status_code == 422
        detail = resp.json()["detail"].lower()
        assert "25" in detail or "size" in detail

    def test_oversized_no_db_record(self) -> None:
        with patch("app.routers.documents.MAX_FILE_SIZE", 100):
            content = b"\x00" * 101
            client.post(
                "/documents",
                files={"file": _make_file(content, "big2.txt")},
                cookies={"session_id": self.session_id},
            )
        assert _document_count() == 0

    def test_oversized_no_file_saved(self) -> None:
        files_before = _files_before()
        with patch("app.routers.documents.MAX_FILE_SIZE", 100):
            content = b"\x00" * 101
            client.post(
                "/documents",
                files={"file": _make_file(content, "big3.txt")},
                cookies={"session_id": self.session_id},
            )
        files_after = _files_before()
        assert files_after == files_before


# ---------------------------------------------------------------------------
# AC-023 — unsupported file type → 422, no file or DB record
# ---------------------------------------------------------------------------


class TestUploadUnsupportedType:
    def setup_method(self) -> None:
        self.admin_email = "us009_admin_type@example.com"
        self.admin_pw = "admin-pw-123"
        _create_user(self.admin_email, self.admin_pw, role="Administrator")
        self.session_id = _login(self.admin_email, self.admin_pw)
        _cleanup_documents()

    def teardown_method(self) -> None:
        _logout(self.session_id)
        _cleanup_documents()
        _delete_user(self.admin_email)

    def test_unsupported_type_rejected_with_422(self) -> None:
        resp = client.post(
            "/documents",
            files={"file": _make_file(b"data", "photo.jpg")},
            cookies={"session_id": self.session_id},
        )
        assert resp.status_code == 422
        detail = resp.json()["detail"].lower()
        assert "unsupported" in detail or "supported" in detail

    def test_unsupported_no_db_record(self) -> None:
        client.post(
            "/documents",
            files={"file": _make_file(b"data", "sheet.xlsx")},
            cookies={"session_id": self.session_id},
        )
        assert _document_count() == 0

    def test_unsupported_no_file_saved(self) -> None:
        files_before = _files_before()
        client.post(
            "/documents",
            files={"file": _make_file(b"data", "file.csv")},
            cookies={"session_id": self.session_id},
        )
        files_after = _files_before()
        assert files_after == files_before

    def test_no_extension_rejected(self) -> None:
        resp = client.post(
            "/documents",
            files={"file": _make_file(b"data", "noextension")},
            cookies={"session_id": self.session_id},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# AC-024 — regular (non-admin) user uploads → 403, no file stored
# ---------------------------------------------------------------------------


class TestUploadNonAdmin:
    def setup_method(self) -> None:
        self.admin_email = "us009_admin_forbidden@example.com"
        self.regular_email = "us009_regular@example.com"
        self.pw = "pw-123"
        _create_user(self.admin_email, self.pw, role="Administrator")
        _create_user(self.regular_email, self.pw, role="Regular User")
        self.regular_session = _login(self.regular_email, self.pw)
        _cleanup_documents()

    def teardown_method(self) -> None:
        _logout(self.regular_session)
        _cleanup_documents()
        _delete_user(self.regular_email)
        _delete_user(self.admin_email)

    def test_regular_user_upload_returns_403(self) -> None:
        resp = client.post(
            "/documents",
            files={"file": _make_file(b"hello", "test.txt")},
            cookies={"session_id": self.regular_session},
        )
        assert resp.status_code == 403

    def test_regular_user_no_db_record(self) -> None:
        client.post(
            "/documents",
            files={"file": _make_file(b"hello", "test2.txt")},
            cookies={"session_id": self.regular_session},
        )
        assert _document_count() == 0

    def test_regular_user_no_file_saved(self) -> None:
        files_before = _files_before()
        client.post(
            "/documents",
            files={"file": _make_file(b"hello", "test3.txt")},
            cookies={"session_id": self.regular_session},
        )
        files_after = _files_before()
        assert files_after == files_before


# ---------------------------------------------------------------------------
# Unauthenticated access → 401
# ---------------------------------------------------------------------------


class TestUnauthenticated:
    def setup_method(self) -> None:
        _cleanup_documents()

    def teardown_method(self) -> None:
        _cleanup_documents()

    def test_unauthenticated_post_returns_401(self) -> None:
        resp = client.post(
            "/documents",
            files={"file": _make_file(b"hello", "test.txt")},
        )
        assert resp.status_code == 401

    def test_unauthenticated_get_returns_401(self) -> None:
        resp = client.get("/documents")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# AC-042 — GET /documents returns list from DB with required fields
# ---------------------------------------------------------------------------


class TestListDocuments:
    def setup_method(self) -> None:
        self.admin_email = "us009_admin_list@example.com"
        self.regular_email = "us009_regular_list@example.com"
        self.pw = "pw-123"
        _create_user(self.admin_email, self.pw, role="Administrator")
        _create_user(self.regular_email, self.pw, role="Regular User")
        self.admin_session = _login(self.admin_email, self.pw)
        self.regular_session = _login(self.regular_email, self.pw)
        _cleanup_documents()

    def teardown_method(self) -> None:
        _logout(self.admin_session)
        _logout(self.regular_session)
        _cleanup_documents()
        _delete_user(self.regular_email)
        _delete_user(self.admin_email)

    def test_get_returns_uploaded_document(self) -> None:
        """An uploaded document must appear in GET /documents."""
        content = b"list test content"
        resp = client.post(
            "/documents",
            files={"file": _make_file(content, "listed.txt")},
            cookies={"session_id": self.admin_session},
        )
        assert resp.status_code == 200
        doc_id = resp.json()["id"]

        resp = client.get("/documents", cookies={"session_id": self.admin_session})
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["id"] == doc_id

    def test_get_returns_all_required_fields(self) -> None:
        """Response items must include filename, type, size, created_at, status."""
        client.post(
            "/documents",
            files={"file": _make_file(b"fields", "fields.pdf")},
            cookies={"session_id": self.admin_session},
        )
        resp = client.get("/documents", cookies={"session_id": self.admin_session})
        assert resp.status_code == 200
        item = resp.json()[0]
        assert "filename" in item
        assert "file_type" in item
        assert "file_size" in item
        assert "created_at" in item
        assert "status" in item
        assert "id" in item
        assert item["filename"] == "fields.pdf"
        assert item["file_type"] == "PDF"
        assert item["file_size"] == 6
        assert item["status"] == "Processing"

    def test_regular_user_can_list_documents(self) -> None:
        """Contract: GET /documents is available to any authenticated user."""
        client.post(
            "/documents",
            files={"file": _make_file(b"reg access", "reg.txt")},
            cookies={"session_id": self.admin_session},
        )
        resp = client.get("/documents", cookies={"session_id": self.regular_session})
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_get_returns_empty_list_when_no_documents(self) -> None:
        resp = client.get("/documents", cookies={"session_id": self.admin_session})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_reads_from_database_not_memory(self) -> None:
        """Inserting a row via ORM is reflected in the API response — the
        endpoint queries the DB, not an in-memory or hardcoded list."""
        with SessionLocal() as db:
            admin = db.execute(select(User).where(User.email == self.admin_email)).scalar_one()
            doc = Document(
                filename="direct-insert.pdf",
                file_type="PDF",
                file_size=42,
                file_path="/tmp/direct-insert.pdf",
                status="Processing",
                uploaded_by=admin.id,
            )
            db.add(doc)
            db.commit()

        resp = client.get("/documents", cookies={"session_id": self.admin_session})
        assert resp.status_code == 200
        items = resp.json()
        assert any(i["filename"] == "direct-insert.pdf" for i in items)


# ---------------------------------------------------------------------------
# AC-045 — GET /documents does not include password hashes or sensitive fields
# ---------------------------------------------------------------------------


class TestNoSensitiveFields:
    def setup_method(self) -> None:
        self.admin_email = "us009_admin_nosensitive@example.com"
        self.admin_pw = "admin-pw-123"
        _create_user(self.admin_email, self.admin_pw, role="Administrator")
        self.session_id = _login(self.admin_email, self.admin_pw)
        _cleanup_documents()

    def teardown_method(self) -> None:
        _logout(self.session_id)
        _cleanup_documents()
        _delete_user(self.admin_email)

    def test_get_documents_excludes_sensitive_fields(self) -> None:
        """No response item may contain password_hash, password, file_path,
        uploaded_by, or updated_at."""
        client.post(
            "/documents",
            files={"file": _make_file(b"sensitive", "check.pdf")},
            cookies={"session_id": self.session_id},
        )
        resp = client.get("/documents", cookies={"session_id": self.session_id})
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) >= 1

        forbidden_keys = {"password_hash", "password", "file_path", "uploaded_by", "updated_at"}
        for item in items:
            keys = set(item.keys())
            leaked = keys & forbidden_keys
            assert not leaked, f"Sensitive fields leaked in response: {leaked}"

    def test_raw_json_does_not_contain_password_hash(self) -> None:
        """The raw JSON body must not contain the string 'password_hash'."""
        client.post(
            "/documents",
            files={"file": _make_file(b"raw", "rawcheck.txt")},
            cookies={"session_id": self.session_id},
        )
        resp = client.get("/documents", cookies={"session_id": self.session_id})
        raw = resp.text
        assert "password_hash" not in raw
        assert "password" not in raw.lower()


# ---------------------------------------------------------------------------
# AC-043 — documents persist across simulated restart
# ---------------------------------------------------------------------------


class TestPersistenceAcrossRestart:
    def setup_method(self) -> None:
        self.admin_email = "us009_admin_persist@example.com"
        self.admin_pw = "admin-pw-123"
        _create_user(self.admin_email, self.admin_pw, role="Administrator")
        self.session_id = _login(self.admin_email, self.admin_pw)
        _cleanup_documents()

    def teardown_method(self) -> None:
        _logout(self.session_id)
        _cleanup_documents()
        _delete_user(self.admin_email)

    def test_documents_survive_new_session_local(self) -> None:
        """After creating a fresh SessionLocal (simulating a restart), the
        document row must still be readable from the database."""
        content = b"survive restart"
        resp = client.post(
            "/documents",
            files={"file": _make_file(content, "persist.txt")},
            cookies={"session_id": self.session_id},
        )
        assert resp.status_code == 200
        doc_id = _to_uuid(resp.json()["id"])

        # Simulate restart: a new SessionLocal reads from the same DB file.
        with SessionLocal() as db:
            doc = db.execute(select(Document).where(Document.id == doc_id)).scalar_one()
            assert doc is not None
            assert doc.filename == "persist.txt"
            assert doc.status == "Processing"

            saved = Path(doc.file_path)
            assert saved.exists()
            assert saved.read_bytes() == content

    def test_documents_visible_via_new_test_client(self) -> None:
        """A new TestClient instance (simulating a new server process) must
        see the previously-uploaded document via GET /documents."""
        content = b"new client persist"
        resp = client.post(
            "/documents",
            files={"file": _make_file(content, "client.txt")},
            cookies={"session_id": self.session_id},
        )
        assert resp.status_code == 200
        doc_id = resp.json()["id"]

        new_client = TestClient(app)
        new_session = _login(self.admin_email, self.admin_pw)
        try:
            resp2 = new_client.get("/documents", cookies={"session_id": new_session})
            assert resp2.status_code == 200
            items = resp2.json()
            assert any(i["id"] == doc_id for i in items)
            assert any(i["filename"] == "client.txt" for i in items)
        finally:
            _logout(new_session)


# ---------------------------------------------------------------------------
# AC-044 — startup does not truncate or delete existing document records
# ---------------------------------------------------------------------------


class TestStartupDoesNotDeleteDocuments:
    def setup_method(self) -> None:
        self.admin_email = "us009_admin_startup@example.com"
        self.admin_pw = "admin-pw-123"
        _create_user(self.admin_email, self.admin_pw, role="Administrator")
        _cleanup_documents()

    def teardown_method(self) -> None:
        _cleanup_documents()
        _delete_user(self.admin_email)

    def test_create_all_does_not_delete_documents(self) -> None:
        """Re-running Base.metadata.create_all (as main.py does on startup)
        must not delete existing document records."""
        with SessionLocal() as db:
            admin = db.execute(select(User).where(User.email == self.admin_email)).scalar_one()
            doc = Document(
                filename="startup-survival.pdf",
                file_type="PDF",
                file_size=99,
                file_path="/tmp/startup-survival.pdf",
                status="Processing",
                uploaded_by=admin.id,
            )
            db.add(doc)
            db.commit()
            doc_id = doc.id

        # Simulate startup: create_all is idempotent (IF NOT EXISTS).
        Base.metadata.create_all(bind=engine)

        with SessionLocal() as db:
            doc = db.execute(select(Document).where(Document.id == doc_id)).scalar_one_or_none()
            assert doc is not None
            assert doc.filename == "startup-survival.pdf"

    def test_seed_admin_does_not_delete_documents(self) -> None:
        """Re-running seed_admin (as main.py does on startup) must not delete
        existing document records."""
        with SessionLocal() as db:
            admin = db.execute(select(User).where(User.email == self.admin_email)).scalar_one()
            doc = Document(
                filename="seed-survival.txt",
                file_type="TXT",
                file_size=50,
                file_path="/tmp/seed-survival.txt",
                status="Processing",
                uploaded_by=admin.id,
            )
            db.add(doc)
            db.commit()
            doc_id = doc.id

        # Simulate startup seeding.
        with SessionLocal() as db:
            seed_admin(db)

        with SessionLocal() as db:
            doc = db.execute(select(Document).where(Document.id == doc_id)).scalar_one_or_none()
            assert doc is not None
            assert doc.filename == "seed-survival.txt"

    def test_full_startup_simulation_preserves_documents(self) -> None:
        """Both create_all and seed_admin together (the full main.py startup
        sequence) must leave existing documents intact."""
        with SessionLocal() as db:
            admin = db.execute(select(User).where(User.email == self.admin_email)).scalar_one()
            doc = Document(
                filename="full-startup.pdf",
                file_type="PDF",
                file_size=77,
                file_path="/tmp/full-startup.pdf",
                status="Processing",
                uploaded_by=admin.id,
            )
            db.add(doc)
            db.commit()
            doc_id = doc.id
            count_before = len(db.execute(select(Document)).scalars().all())

        # Simulate full startup sequence.
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            seed_admin(db)

        with SessionLocal() as db:
            doc = db.execute(select(Document).where(Document.id == doc_id)).scalar_one_or_none()
            assert doc is not None
            assert doc.filename == "full-startup.pdf"
            count_after = len(db.execute(select(Document)).scalars().all())
            assert count_after == count_before


# ---------------------------------------------------------------------------
# US-017-1 — GET /documents/{id} and GET /documents/{id}/download
# ---------------------------------------------------------------------------


class TestGetDocumentDetail:
    """AC-048 / AC-049 — GET /documents/{id} full metadata and 404."""

    def setup_method(self) -> None:
        self.admin_email = "us017_admin_detail@example.com"
        self.regular_email = "us017_regular_detail@example.com"
        self.pw = "pw-123"
        _create_user(self.admin_email, self.pw, role="Administrator")
        _create_user(self.regular_email, self.pw, role="Regular User")
        self.admin_session = _login(self.admin_email, self.pw)
        self.regular_session = _login(self.regular_email, self.pw)
        _cleanup_documents()

    def teardown_method(self) -> None:
        _logout(self.admin_session)
        _logout(self.regular_session)
        _cleanup_documents()
        _delete_user(self.regular_email)
        _delete_user(self.admin_email)

    def test_get_detail_returns_full_metadata(self) -> None:
        """AC-048: existing document returns filename, type, size, upload
        date, status, failure reason, created_at, updated_at."""
        content = b"detail metadata content"
        resp = client.post(
            "/documents",
            files={"file": _make_file(content, "detail.pdf")},
            cookies={"session_id": self.admin_session},
        )
        assert resp.status_code == 200
        doc_id = resp.json()["id"]

        resp = client.get(f"/documents/{doc_id}", cookies={"session_id": self.admin_session})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["id"] == doc_id
        assert body["filename"] == "detail.pdf"
        assert body["file_type"] == "PDF"
        assert body["file_size"] == len(content)
        assert body["status"] == "Processing"
        assert "failure_reason" in body
        assert body["failure_reason"] is None
        assert "created_at" in body
        assert "updated_at" in body

    def test_get_detail_includes_failure_reason_when_set(self) -> None:
        """AC-048: failure_reason must be returned when it is set on the doc."""
        content = b"failed doc content"
        resp = client.post(
            "/documents",
            files={"file": _make_file(content, "failed.txt")},
            cookies={"session_id": self.admin_session},
        )
        assert resp.status_code == 200
        doc_id = _to_uuid(resp.json()["id"])

        with SessionLocal() as db:
            doc = db.execute(select(Document).where(Document.id == doc_id)).scalar_one()
            doc.status = "Failed"
            doc.failure_reason = "Extraction failed: unsupported encoding"
            db.commit()

        resp = client.get(f"/documents/{doc_id}", cookies={"session_id": self.admin_session})
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "Failed"
        assert body["failure_reason"] == "Extraction failed: unsupported encoding"

    def test_get_detail_regular_user_can_access(self) -> None:
        """Any authenticated user may call GET /documents/{id}."""
        content = b"regular access detail"
        resp = client.post(
            "/documents",
            files={"file": _make_file(content, "reg_access.txt")},
            cookies={"session_id": self.admin_session},
        )
        doc_id = resp.json()["id"]

        resp = client.get(f"/documents/{doc_id}", cookies={"session_id": self.regular_session})
        assert resp.status_code == 200
        assert resp.json()["filename"] == "reg_access.txt"

    def test_get_detail_nonexistent_id_returns_404(self) -> None:
        """AC-049: non-existent ID returns 404 Not Found."""
        fake_id = str(uuid_mod.uuid4())
        resp = client.get(f"/documents/{fake_id}", cookies={"session_id": self.admin_session})
        assert resp.status_code == 404


class TestDownloadDocument:
    """AC-050 / AC-051 — GET /documents/{id}/download streaming and missing file."""

    def setup_method(self) -> None:
        self.admin_email = "us017_admin_download@example.com"
        self.regular_email = "us017_regular_download@example.com"
        self.pw = "pw-123"
        _create_user(self.admin_email, self.pw, role="Administrator")
        _create_user(self.regular_email, self.pw, role="Regular User")
        self.admin_session = _login(self.admin_email, self.pw)
        self.regular_session = _login(self.regular_email, self.pw)
        _cleanup_documents()

    def teardown_method(self) -> None:
        _logout(self.admin_session)
        _logout(self.regular_session)
        _cleanup_documents()
        _delete_user(self.regular_email)
        _delete_user(self.admin_email)

    def test_download_streams_original_file(self) -> None:
        """AC-050: download streams the original file content."""
        content = b"download me please"
        resp = client.post(
            "/documents",
            files={"file": _make_file(content, "download.txt")},
            cookies={"session_id": self.admin_session},
        )
        assert resp.status_code == 200
        doc_id = resp.json()["id"]

        resp = client.get(
            f"/documents/{doc_id}/download", cookies={"session_id": self.admin_session}
        )
        assert resp.status_code == 200, resp.text
        assert resp.content == content

    def test_download_content_disposition_has_filename(self) -> None:
        """AC-050: Content-Disposition attachment header includes the filename."""
        content = b"disposition check"
        resp = client.post(
            "/documents",
            files={"file": _make_file(content, "disposition.pdf")},
            cookies={"session_id": self.admin_session},
        )
        doc_id = resp.json()["id"]

        resp = client.get(
            f"/documents/{doc_id}/download", cookies={"session_id": self.admin_session}
        )
        assert resp.status_code == 200
        cd = resp.headers.get("content-disposition", "")
        assert "attachment" in cd
        assert "disposition.pdf" in cd

    def test_download_correct_content_type(self) -> None:
        """AC-050: content type derived from file_type/extension."""
        cases = [
            ("doc.pdf", "application/pdf"),
            ("doc.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            ("doc.txt", "text/plain"),
            ("doc.md", "text/markdown"),
        ]
        for filename, expected_ct in cases:
            content = b"content for " + filename.encode()
            resp = client.post(
                "/documents",
                files={"file": _make_file(content, filename)},
                cookies={"session_id": self.admin_session},
            )
            assert resp.status_code == 200, resp.text
            doc_id = resp.json()["id"]

            resp = client.get(
                f"/documents/{doc_id}/download", cookies={"session_id": self.admin_session}
            )
            assert resp.status_code == 200, f"failed for {filename}"
            ct = resp.headers.get("content-type", "")
            assert ct.split(";")[0].strip() == expected_ct, (
                f"content-type for {filename}: got {ct!r}, expected {expected_ct!r}"
            )

    def test_download_regular_user_can_access(self) -> None:
        """Any authenticated user may download documents."""
        content = b"regular download content"
        resp = client.post(
            "/documents",
            files={"file": _make_file(content, "reg_dl.txt")},
            cookies={"session_id": self.admin_session},
        )
        doc_id = resp.json()["id"]

        resp = client.get(
            f"/documents/{doc_id}/download", cookies={"session_id": self.regular_session}
        )
        assert resp.status_code == 200
        assert resp.content == content

    def test_download_nonexistent_id_returns_404(self) -> None:
        """Non-existent document ID returns 404."""
        fake_id = str(uuid_mod.uuid4())
        resp = client.get(
            f"/documents/{fake_id}/download", cookies={"session_id": self.admin_session}
        )
        assert resp.status_code == 404

    def test_download_file_missing_from_disk_returns_error(self) -> None:
        """AC-051: DB record exists but file missing from disk → clear error."""
        content = b"will be deleted from disk"
        resp = client.post(
            "/documents",
            files={"file": _make_file(content, "ghost.txt")},
            cookies={"session_id": self.admin_session},
        )
        assert resp.status_code == 200
        doc_id = _to_uuid(resp.json()["id"])

        # Remove the file from disk but keep the DB record.
        with SessionLocal() as db:
            doc = db.execute(select(Document).where(Document.id == doc_id)).scalar_one()
            file_path = Path(doc.file_path)
        assert file_path.exists()
        file_path.unlink()
        assert not file_path.exists()

        resp = client.get(
            f"/documents/{doc_id}/download", cookies={"session_id": self.admin_session}
        )
        assert resp.status_code == 404
        detail = resp.json()["detail"].lower()
        assert "missing" in detail

    def test_download_file_missing_error_message_is_clear(self) -> None:
        """AC-051: error message explicitly says the file is missing from storage."""
        content = b"ghost 2"
        resp = client.post(
            "/documents",
            files={"file": _make_file(content, "ghost2.md")},
            cookies={"session_id": self.admin_session},
        )
        doc_id = _to_uuid(resp.json()["id"])

        with SessionLocal() as db:
            doc = db.execute(select(Document).where(Document.id == doc_id)).scalar_one()
            Path(doc.file_path).unlink()

        resp = client.get(
            f"/documents/{doc_id}/download", cookies={"session_id": self.admin_session}
        )
        assert resp.status_code == 404
        assert "missing" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# US-017-1 — unauthenticated access to GET /documents/{id} and download
# ---------------------------------------------------------------------------


class TestGetDownloadUnauthenticated:
    """Both new endpoints require authentication via session cookie."""

    def setup_method(self) -> None:
        _cleanup_documents()

    def teardown_method(self) -> None:
        _cleanup_documents()

    def test_get_detail_unauthenticated_returns_401(self) -> None:
        fake_id = str(uuid_mod.uuid4())
        resp = client.get(f"/documents/{fake_id}")
        assert resp.status_code == 401

    def test_download_unauthenticated_returns_401(self) -> None:
        fake_id = str(uuid_mod.uuid4())
        resp = client.get(f"/documents/{fake_id}/download")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# US-019-1 — DELETE /documents/{id} with cascading cleanup
# ---------------------------------------------------------------------------


class TestDeleteDocumentAdmin:
    """AC-052 / AC-053 / AC-054 — admin DELETE removes file, document,
    chunks, embeddings, and citations; subsequent GET excludes it."""

    def setup_method(self) -> None:
        self.admin_email = "us019_admin_delete@example.com"
        self.admin_pw = "admin-pw-123"
        _create_user(self.admin_email, self.admin_pw, role="Administrator")
        self.session_id = _login(self.admin_email, self.admin_pw)
        _cleanup_documents()

    def teardown_method(self) -> None:
        _logout(self.session_id)
        _cleanup_documents()
        _delete_user(self.admin_email)

    def _upload_doc_with_chunks_and_citations(self) -> tuple[str, Path]:
        """Upload a document, add chunks + citations, return (doc_id, file_path)."""
        content = b"document to be deleted"
        resp = client.post(
            "/documents",
            files={"file": _make_file(content, "delete-me.txt")},
            cookies={"session_id": self.session_id},
        )
        assert resp.status_code == 200
        doc_id = resp.json()["id"]
        doc_uuid = _to_uuid(doc_id)

        with SessionLocal() as db:
            admin = db.execute(
                select(User).where(User.email == self.admin_email)
            ).scalar_one()
            admin_id = admin.id

        _create_chunks_and_citations(doc_uuid, admin_id)

        with SessionLocal() as db:
            doc = db.execute(
                select(Document).where(Document.id == doc_uuid)
            ).scalar_one()
            file_path = Path(doc.file_path)

        return doc_id, file_path

    def test_delete_returns_message_response(self) -> None:
        """AC-052: successful deletion returns MessageResponse JSON."""
        doc_id, _ = self._upload_doc_with_chunks_and_citations()
        resp = client.delete(
            f"/documents/{doc_id}", cookies={"session_id": self.session_id}
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["message"] == "Document deleted successfully"

    def test_delete_removes_file_from_filesystem(self) -> None:
        """AC-052: the stored file is removed from the filesystem."""
        doc_id, file_path = self._upload_doc_with_chunks_and_citations()
        assert file_path.exists()
        client.delete(f"/documents/{doc_id}", cookies={"session_id": self.session_id})
        assert not file_path.exists()

    def test_delete_removes_document_record(self) -> None:
        """AC-052: the Document DB record is removed."""
        doc_id, _ = self._upload_doc_with_chunks_and_citations()
        doc_uuid = _to_uuid(doc_id)
        client.delete(f"/documents/{doc_id}", cookies={"session_id": self.session_id})

        with SessionLocal() as db:
            doc = db.execute(
                select(Document).where(Document.id == doc_uuid)
            ).scalar_one_or_none()
            assert doc is None

    def test_delete_removes_chunks_and_embeddings(self) -> None:
        """AC-052 / AC-054: all chunks (and their embeddings) are removed."""
        doc_id, _ = self._upload_doc_with_chunks_and_citations()
        doc_uuid = _to_uuid(doc_id)
        client.delete(f"/documents/{doc_id}", cookies={"session_id": self.session_id})

        with SessionLocal() as db:
            chunks = db.execute(
                select(Chunk).where(Chunk.document_id == doc_uuid)
            ).scalars().all()
            assert len(chunks) == 0

    def test_delete_removes_citations(self) -> None:
        """AC-052: all citations referencing the document are removed."""
        doc_id, _ = self._upload_doc_with_chunks_and_citations()
        doc_uuid = _to_uuid(doc_id)
        client.delete(f"/documents/{doc_id}", cookies={"session_id": self.session_id})

        with SessionLocal() as db:
            citations = db.execute(
                select(Citation).where(Citation.document_id == doc_uuid)
            ).scalars().all()
            assert len(citations) == 0

    def test_delete_excludes_from_get_documents(self) -> None:
        """AC-053: after deletion, GET /documents does not include the doc."""
        doc_id, _ = self._upload_doc_with_chunks_and_citations()
        client.delete(f"/documents/{doc_id}", cookies={"session_id": self.session_id})

        resp = client.get("/documents", cookies={"session_id": self.session_id})
        assert resp.status_code == 200
        items = resp.json()
        assert not any(i["id"] == doc_id for i in items)
        assert len(items) == 0

    def test_delete_then_get_detail_returns_404(self) -> None:
        """AC-053: after deletion, GET /documents/{id} returns 404."""
        doc_id, _ = self._upload_doc_with_chunks_and_citations()
        client.delete(f"/documents/{doc_id}", cookies={"session_id": self.session_id})

        resp = client.get(f"/documents/{doc_id}", cookies={"session_id": self.session_id})
        assert resp.status_code == 404

    def test_delete_chunks_empty_for_document_id(self) -> None:
        """AC-054: chunks table is empty for the deleted document_id."""
        doc_id, _ = self._upload_doc_with_chunks_and_citations()
        doc_uuid = _to_uuid(doc_id)

        # Verify chunks exist before deletion
        with SessionLocal() as db:
            chunks_before = db.execute(
                select(Chunk).where(Chunk.document_id == doc_uuid)
            ).scalars().all()
            assert len(chunks_before) == 2

        client.delete(f"/documents/{doc_id}", cookies={"session_id": self.session_id})

        with SessionLocal() as db:
            chunks_after = db.execute(
                select(Chunk).where(Chunk.document_id == doc_uuid)
            ).scalars().all()
            assert len(chunks_after) == 0

    def test_delete_file_already_removed_from_disk(self) -> None:
        """Deletion succeeds even when the file is already gone from disk."""
        doc_id, file_path = self._upload_doc_with_chunks_and_citations()
        file_path.unlink()  # simulate file already gone
        assert not file_path.exists()

        resp = client.delete(f"/documents/{doc_id}", cookies={"session_id": self.session_id})
        assert resp.status_code == 200
        assert resp.json()["message"] == "Document deleted successfully"

        doc_uuid = _to_uuid(doc_id)
        with SessionLocal() as db:
            doc = db.execute(
                select(Document).where(Document.id == doc_uuid)
            ).scalar_one_or_none()
            assert doc is None


class TestDeleteDocumentNonAdmin:
    """AC-055 — regular (non-admin) user DELETE → 403, no data removed."""

    def setup_method(self) -> None:
        self.admin_email = "us019_admin_for_403@example.com"
        self.regular_email = "us019_regular_delete@example.com"
        self.pw = "pw-123"
        _create_user(self.admin_email, self.pw, role="Administrator")
        _create_user(self.regular_email, self.pw, role="Regular User")
        self.admin_session = _login(self.admin_email, self.pw)
        self.regular_session = _login(self.regular_email, self.pw)
        _cleanup_documents()

    def teardown_method(self) -> None:
        _logout(self.admin_session)
        _logout(self.regular_session)
        _cleanup_documents()
        _delete_user(self.regular_email)
        _delete_user(self.admin_email)

    def test_regular_user_delete_returns_403(self) -> None:
        """AC-055: non-admin DELETE → 403 Forbidden."""
        content = b"protected document"
        resp = client.post(
            "/documents",
            files={"file": _make_file(content, "protected.txt")},
            cookies={"session_id": self.admin_session},
        )
        doc_id = resp.json()["id"]

        resp = client.delete(
            f"/documents/{doc_id}", cookies={"session_id": self.regular_session}
        )
        assert resp.status_code == 403

    def test_regular_user_delete_no_data_removed(self) -> None:
        """AC-055: after 403, the document and its file are still present."""
        content = b"protected document 2"
        resp = client.post(
            "/documents",
            files={"file": _make_file(content, "protected2.txt")},
            cookies={"session_id": self.admin_session},
        )
        doc_id = resp.json()["id"]
        doc_uuid = _to_uuid(doc_id)

        client.delete(f"/documents/{doc_id}", cookies={"session_id": self.regular_session})

        with SessionLocal() as db:
            doc = db.execute(
                select(Document).where(Document.id == doc_uuid)
            ).scalar_one_or_none()
            assert doc is not None
            assert doc.filename == "protected2.txt"

        # File still on disk
        with SessionLocal() as db:
            doc = db.execute(
                select(Document).where(Document.id == doc_uuid)
            ).scalar_one()
            assert Path(doc.file_path).exists()

    def test_regular_user_delete_no_chunks_removed(self) -> None:
        """AC-055: after 403, any chunks associated with the document remain."""
        content = b"protected document 3"
        resp = client.post(
            "/documents",
            files={"file": _make_file(content, "protected3.txt")},
            cookies={"session_id": self.admin_session},
        )
        doc_id = resp.json()["id"]
        doc_uuid = _to_uuid(doc_id)

        with SessionLocal() as db:
            admin = db.execute(
                select(User).where(User.email == self.admin_email)
            ).scalar_one()
            admin_id = admin.id
        _create_chunks_and_citations(doc_uuid, admin_id)

        client.delete(f"/documents/{doc_id}", cookies={"session_id": self.regular_session})

        with SessionLocal() as db:
            chunks = db.execute(
                select(Chunk).where(Chunk.document_id == doc_uuid)
            ).scalars().all()
            assert len(chunks) == 2


class TestDeleteDocumentNotFound:
    """DELETE on a non-existent document ID returns 404 Not Found."""

    def setup_method(self) -> None:
        self.admin_email = "us019_admin_404@example.com"
        self.admin_pw = "admin-pw-123"
        _create_user(self.admin_email, self.admin_pw, role="Administrator")
        self.session_id = _login(self.admin_email, self.admin_pw)
        _cleanup_documents()

    def teardown_method(self) -> None:
        _logout(self.session_id)
        _cleanup_documents()
        _delete_user(self.admin_email)

    def test_delete_nonexistent_id_returns_404(self) -> None:
        fake_id = str(uuid_mod.uuid4())
        resp = client.delete(f"/documents/{fake_id}", cookies={"session_id": self.session_id})
        assert resp.status_code == 404


class TestDeleteDocumentUnauthenticated:
    """Unauthenticated DELETE → 401."""

    def setup_method(self) -> None:
        _cleanup_documents()

    def teardown_method(self) -> None:
        _cleanup_documents()

    def test_unauthenticated_delete_returns_401(self) -> None:
        fake_id = str(uuid_mod.uuid4())
        resp = client.delete(f"/documents/{fake_id}")
        assert resp.status_code == 401