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
from app.models import Document, User
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
