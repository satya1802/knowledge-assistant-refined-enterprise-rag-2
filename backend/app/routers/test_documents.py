"""Integration tests for POST /documents and GET /documents (US-009-1).

These tests live inside ``backend/app/routers/`` because the task scope
restricts writes to that directory.  They replicate the test-database
bootstrap that ``backend/tests/conftest.py`` performs so they can run
standalone with ``pytest backend/app/routers/test_documents.py``.

Covers:
  AC-021 — admin uploads PDF/DOCX/TXT/MD ≤ 25 MB; file saved to
           backend/uploads, Document DB record created with status='Processing'.
  AC-022 — upload > 25 MB → 422 size-limit error, no file or DB record.
  AC-023 — unsupported file type → 422 supported-types error, no file/DB record.
  AC-024 — non-admin upload → 403, no file stored.
  AC-025 — file persisted in backend/uploads (durable filesystem).
  AC-042 — GET /documents reads from the database.
  AC-043 — file and DB record remain intact across restarts (verified by
           re-querying after clearing the session-level cache).
  AC-046 — GET /documents returns filename, type, size, upload date, status.
  Contract — unauthenticated POST/GET → 401; regular user GET → 200.
"""

from __future__ import annotations

import os
import uuid as uuid_mod
from pathlib import Path

# Point at a throwaway database and remove any pre-existing files BEFORE
# importing the application (which creates tables at import time).
os.environ["DATABASE_URL"] = "sqlite:///./test_documents_router.db"
for _name in ("app.db", "test_documents_router.db"):
    _p = Path(_name)
    if _p.exists():
        _p.unlink()

import bcrypt  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Document, User  # noqa: E402
from app.routers.documents import UPLOAD_DIR  # noqa: E402

client = TestClient(app)

_MAX_SIZE = 25 * 1024 * 1024


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _logout(session_id: str) -> None:
    client.post("/auth/logout", cookies={"session_id": session_id})


def _cleanup_documents() -> None:
    """Delete all Document rows and remove their files from uploads."""
    with SessionLocal() as db:
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


# ---------------------------------------------------------------------------
# AC-021 — admin uploads a supported file ≤ 25 MB
# ---------------------------------------------------------------------------


class TestUploadSuccess:
    def setup_method(self) -> None:
        self.admin_email = "ac021_admin@example.com"
        self.admin_pw = "admin-pw-123"
        _create_user(self.admin_email, self.admin_pw, role="Administrator")
        self.session_id = _login(self.admin_email, self.admin_pw)
        _cleanup_documents()

    def teardown_method(self) -> None:
        _logout(self.session_id)
        _cleanup_documents()
        _delete_user(self.admin_email)

    def test_admin_uploads_txt_file(self) -> None:
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
        assert "id" in body
        assert "created_at" in body

    def test_admin_uploads_pdf_file(self) -> None:
        content = b"%PDF-1.4 fake pdf content"
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

    def test_admin_uploads_docx_file(self) -> None:
        content = b"PK\x03\x04 fake docx"
        resp = client.post(
            "/documents",
            files={"file": _make_file(content, "doc.docx")},
            cookies={"session_id": self.session_id},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["file_type"] == "DOCX"

    def test_admin_uploads_md_file(self) -> None:
        content = b"# Markdown heading"
        resp = client.post(
            "/documents",
            files={"file": _make_file(content, "readme.md")},
            cookies={"session_id": self.session_id},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["file_type"] == "MD"

    def test_file_saved_to_uploads_directory(self) -> None:
        """AC-025: file persisted in backend/uploads durable directory."""
        content = b"persisted content"
        resp = client.post(
            "/documents",
            files={"file": _make_file(content, "persist.txt")},
            cookies={"session_id": self.session_id},
        )
        assert resp.status_code == 200
        doc_id = _to_uuid(resp.json()["id"])

        # File exists on disk in the uploads directory.
        with SessionLocal() as db:
            doc = db.execute(select(Document).where(Document.id == doc_id)).scalar_one()
            saved = Path(doc.file_path)
            assert saved.exists()
            assert saved.parent == UPLOAD_DIR.resolve()
            assert saved.read_bytes() == content

    def test_db_record_created_with_processing_status(self) -> None:
        """AC-021: Document DB record created with status='Processing'."""
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

    def test_upload_at_exact_25mb_boundary(self) -> None:
        """File exactly 25 MB should be accepted."""
        content = b"\x00" * _MAX_SIZE
        resp = client.post(
            "/documents",
            files={"file": _make_file(content, "exact.txt")},
            cookies={"session_id": self.session_id},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["file_size"] == _MAX_SIZE


# ---------------------------------------------------------------------------
# AC-022 — upload exceeds 25 MB → 422, no file or DB record
# ---------------------------------------------------------------------------


class TestUploadSizeLimit:
    def setup_method(self) -> None:
        self.admin_email = "ac022_admin@example.com"
        self.admin_pw = "admin-pw-123"
        _create_user(self.admin_email, self.admin_pw, role="Administrator")
        self.session_id = _login(self.admin_email, self.admin_pw)
        _cleanup_documents()

    def teardown_method(self) -> None:
        _logout(self.session_id)
        _cleanup_documents()
        _delete_user(self.admin_email)

    def test_oversized_file_rejected_with_422(self) -> None:
        content = b"\x00" * (_MAX_SIZE + 1)
        resp = client.post(
            "/documents",
            files={"file": _make_file(content, "big.txt")},
            cookies={"session_id": self.session_id},
        )
        assert resp.status_code == 422
        detail = resp.json()["detail"].lower()
        assert "25" in detail or "size" in detail

    def test_oversized_no_db_record_created(self) -> None:
        content = b"\x00" * (_MAX_SIZE + 1)
        client.post(
            "/documents",
            files={"file": _make_file(content, "big2.txt")},
            cookies={"session_id": self.session_id},
        )
        assert _document_count() == 0

    def test_oversized_no_file_saved(self) -> None:
        files_before = set(UPLOAD_DIR.glob("*"))
        content = b"\x00" * (_MAX_SIZE + 1)
        client.post(
            "/documents",
            files={"file": _make_file(content, "big3.txt")},
            cookies={"session_id": self.session_id},
        )
        files_after = set(UPLOAD_DIR.glob("*"))
        # No new files should have been created.
        assert files_after == files_before


# ---------------------------------------------------------------------------
# AC-023 — unsupported file type → 422, no file or DB record
# ---------------------------------------------------------------------------


class TestUploadUnsupportedType:
    def setup_method(self) -> None:
        self.admin_email = "ac023_admin@example.com"
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
        files_before = set(UPLOAD_DIR.glob("*"))
        client.post(
            "/documents",
            files={"file": _make_file(b"data", "file.csv")},
            cookies={"session_id": self.session_id},
        )
        files_after = set(UPLOAD_DIR.glob("*"))
        assert files_after == files_before

    def test_no_extension_rejected(self) -> None:
        resp = client.post(
            "/documents",
            files={"file": _make_file(b"data", "noextension")},
            cookies={"session_id": self.session_id},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# AC-024 — non-admin upload → 403, no file stored
# ---------------------------------------------------------------------------


class TestUploadNonAdmin:
    def setup_method(self) -> None:
        self.admin_email = "ac024_admin@example.com"
        self.regular_email = "ac024_regular@example.com"
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

    def test_non_admin_upload_returns_403(self) -> None:
        resp = client.post(
            "/documents",
            files={"file": _make_file(b"hello", "test.txt")},
            cookies={"session_id": self.regular_session},
        )
        assert resp.status_code == 403

    def test_non_admin_no_db_record(self) -> None:
        client.post(
            "/documents",
            files={"file": _make_file(b"hello", "test2.txt")},
            cookies={"session_id": self.regular_session},
        )
        assert _document_count() == 0

    def test_non_admin_no_file_saved(self) -> None:
        files_before = set(UPLOAD_DIR.glob("*"))
        client.post(
            "/documents",
            files={"file": _make_file(b"hello", "test3.txt")},
            cookies={"session_id": self.regular_session},
        )
        files_after = set(UPLOAD_DIR.glob("*"))
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
# AC-042 / AC-046 — GET /documents reads from the database
# ---------------------------------------------------------------------------


class TestListDocuments:
    def setup_method(self) -> None:
        self.admin_email = "ac042_admin@example.com"
        self.regular_email = "ac042_regular@example.com"
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
        """AC-042: document appears in GET /documents after upload."""
        content = b"list test content"
        resp = client.post(
            "/documents",
            files={"file": _make_file(content, "listed.txt")},
            cookies={"session_id": self.admin_session},
        )
        assert resp.status_code == 200
        doc_id = resp.json()["id"]

        # GET as admin
        resp = client.get("/documents", cookies={"session_id": self.admin_session})
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["id"] == doc_id

    def test_get_returns_all_required_fields(self) -> None:
        """AC-046: response includes filename, type, size, upload date, status."""
        client.post(
            "/documents",
            files={"file": _make_file(b"fields", "fields.pdf")},
            cookies={"session_id": self.admin_session},
        )
        resp = client.get("/documents", cookies={"session_id": self.admin_session})
        assert resp.status_code == 200
        item = resp.json()[0]
        assert "id" in item
        assert "filename" in item
        assert "file_type" in item
        assert "file_size" in item
        assert "status" in item
        assert "created_at" in item
        assert "failure_reason" in item
        assert item["filename"] == "fields.pdf"
        assert item["file_type"] == "PDF"
        assert item["file_size"] == 6
        assert item["status"] == "Processing"
        assert item["failure_reason"] is None

    def test_regular_user_can_list_documents(self) -> None:
        """Contract: GET /documents available to any authenticated user."""
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
        """AC-042/AC-044: GET queries DB directly; inserting a row via ORM
        is reflected in the API response without any upload call."""
        with SessionLocal() as db:
            doc = Document(
                filename="direct.pdf",
                file_type="PDF",
                file_size=42,
                file_path="/tmp/direct.pdf",
                status="Processing",
                uploaded_by=db.execute(select(User).where(User.email == self.admin_email))
                .scalar_one()
                .id,
            )
            db.add(doc)
            db.commit()

        resp = client.get("/documents", cookies={"session_id": self.admin_session})
        assert resp.status_code == 200
        items = resp.json()
        assert any(i["filename"] == "direct.pdf" for i in items)


# ---------------------------------------------------------------------------
# AC-043 — file and DB record remain intact after restart
# ---------------------------------------------------------------------------


class TestPersistenceAcrossRestart:
    def setup_method(self) -> None:
        self.admin_email = "ac043_admin@example.com"
        self.pw = "pw-123"
        _create_user(self.admin_email, self.pw, role="Administrator")
        self.session_id = _login(self.admin_email, self.pw)
        _cleanup_documents()

    def teardown_method(self) -> None:
        _logout(self.session_id)
        _cleanup_documents()
        _delete_user(self.admin_email)

    def test_file_and_record_survive_new_client_instance(self) -> None:
        """AC-043: Simulate a 'restart' by creating a new TestClient and
        verifying the DB record and file are still present."""
        content = b"survive restart"
        resp = client.post(
            "/documents",
            files={"file": _make_file(content, "persist.txt")},
            cookies={"session_id": self.session_id},
        )
        assert resp.status_code == 200
        doc_id = _to_uuid(resp.json()["id"])

        # Capture file path and content hash before "restart".
        with SessionLocal() as db:
            doc = db.execute(select(Document).where(Document.id == doc_id)).scalar_one()
            saved_path = Path(doc.file_path)
            assert saved_path.exists()

        # Simulate restart: create a new TestClient (re-imports app state
        # is already loaded, but the DB is persistent on disk).
        new_client = TestClient(app)
        new_session = _login(self.admin_email, self.pw)
        try:
            resp2 = new_client.get("/documents", cookies={"session_id": new_session})
            assert resp2.status_code == 200
            items = resp2.json()
            assert any(i["id"] == str(doc_id) for i in items)
            assert saved_path.exists()
            assert saved_path.read_bytes() == content
        finally:
            _logout(new_session)
