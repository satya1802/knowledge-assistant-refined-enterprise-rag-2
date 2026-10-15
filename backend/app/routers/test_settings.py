"""Integration tests for GET /settings and PATCH /settings (US-031-1).

These tests live inside ``backend/app/routers/`` because the task scope
restricts writes to that directory.  They replicate the test-database
bootstrap that ``backend/tests/conftest.py`` performs so they can run
standalone with ``pytest backend/app/routers/test_settings.py``.

Covers:
  AC-085 — admin GET /settings returns the four fields.
  AC-086 — regular user GET /settings → 403 Forbidden.
  AC-087 — admin PATCH /settings updates the DB, persists across restarts,
           and returns the updated values.
  AC-088 — after updating cosine_threshold, get_current_settings returns the
           new value from the DB at query time.
  AC-089 — after updating Gemini model names, get_current_settings returns
           the new model names from the DB.
  AC-090 — regular user PATCH /settings → 403 Forbidden.
"""

from __future__ import annotations

import os
from pathlib import Path

# Point at a throwaway database and remove any pre-existing files BEFORE
# importing the application (which creates tables at import time).
os.environ["DATABASE_URL"] = "sqlite:///./test_settings_router.db"
for _name in ("app.db", "test_settings_router.db"):
    _p = Path(_name)
    if _p.exists():
        _p.unlink()

import bcrypt  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Settings, User  # noqa: E402
from app.services import get_current_settings  # noqa: E402

client = TestClient(app)


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


def _cleanup_settings() -> None:
    with SessionLocal() as db:
        settings = db.execute(select(Settings).where(Settings.id == 1)).scalar_one_or_none()
        if settings is not None:
            db.delete(settings)
        db.commit()


def _get_settings_row() -> Settings | None:
    with SessionLocal() as db:
        return db.execute(select(Settings).where(Settings.id == 1)).scalar_one_or_none()


# ---------------------------------------------------------------------------
# AC-085 — admin GET /settings returns the four fields
# ---------------------------------------------------------------------------


class TestAdminGetSettings:
    def setup_method(self) -> None:
        self.admin_email = "us031_admin_get@example.com"
        self.admin_pw = "admin-pw-123"
        _create_user(self.admin_email, self.admin_pw, role="Administrator")
        self.session_id = _login(self.admin_email, self.admin_pw)
        _cleanup_settings()

    def teardown_method(self) -> None:
        _logout(self.session_id)
        _cleanup_settings()
        _delete_user(self.admin_email)

    def test_get_returns_all_four_fields(self) -> None:
        resp = client.get("/settings", cookies={"session_id": self.session_id})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "gemini_answer_model" in body
        assert "gemini_embedding_model" in body
        assert "cosine_threshold" in body
        assert "cookie_secure_flag" in body

    def test_get_returns_default_values_when_no_row(self) -> None:
        """When the singleton row does not exist, GET returns the model defaults."""
        assert _get_settings_row() is None
        resp = client.get("/settings", cookies={"session_id": self.session_id})
        assert resp.status_code == 200
        body = resp.json()
        assert body["gemini_answer_model"] == "gemini-2.0-flash"
        assert body["gemini_embedding_model"] == "text-embedding-004"
        assert body["cosine_threshold"] == 0.75
        assert body["cookie_secure_flag"] is True

    def test_get_creates_singleton_row_on_first_access(self) -> None:
        assert _get_settings_row() is None
        client.get("/settings", cookies={"session_id": self.session_id})
        assert _get_settings_row() is not None


# ---------------------------------------------------------------------------
# AC-086 — regular user GET /settings → 403
# ---------------------------------------------------------------------------


class TestRegularUserGetSettings:
    def setup_method(self) -> None:
        self.regular_email = "us031_regular_get@example.com"
        self.pw = "pw-123"
        _create_user(self.regular_email, self.pw, role="Regular User")
        self.session_id = _login(self.regular_email, self.pw)

    def teardown_method(self) -> None:
        _logout(self.session_id)
        _delete_user(self.regular_email)

    def test_regular_user_get_returns_403(self) -> None:
        resp = client.get("/settings", cookies={"session_id": self.session_id})
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# AC-087 — admin PATCH updates DB, persists across restarts, returns updated
# ---------------------------------------------------------------------------


class TestAdminPatchSettings:
    def setup_method(self) -> None:
        self.admin_email = "us031_admin_patch@example.com"
        self.admin_pw = "admin-pw-123"
        _create_user(self.admin_email, self.admin_pw, role="Administrator")
        self.session_id = _login(self.admin_email, self.admin_pw)
        _cleanup_settings()

    def teardown_method(self) -> None:
        _logout(self.session_id)
        _cleanup_settings()
        _delete_user(self.admin_email)

    def test_patch_updates_all_fields_and_returns_them(self) -> None:
        resp = client.patch(
            "/settings",
            json={
                "gemini_answer_model": "gemini-1.5-pro",
                "gemini_embedding_model": "text-embedding-005",
                "cosine_threshold": 0.82,
                "cookie_secure_flag": False,
            },
            cookies={"session_id": self.session_id},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["gemini_answer_model"] == "gemini-1.5-pro"
        assert body["gemini_embedding_model"] == "text-embedding-005"
        assert body["cosine_threshold"] == 0.82
        assert body["cookie_secure_flag"] is False

    def test_patch_persists_to_database(self) -> None:
        client.patch(
            "/settings",
            json={"cosine_threshold": 0.90},
            cookies={"session_id": self.session_id},
        )
        row = _get_settings_row()
        assert row is not None
        assert row.cosine_threshold == 0.90

    def test_patch_persists_across_new_session(self) -> None:
        """A fresh SessionLocal (simulating a restart) reads the updated values."""
        client.patch(
            "/settings",
            json={"gemini_answer_model": "gemini-pro"},
            cookies={"session_id": self.session_id},
        )
        with SessionLocal() as db:
            settings = get_current_settings(db)
            assert settings.gemini_answer_model == "gemini-pro"

    def test_patch_partial_update_only_changes_provided_field(self) -> None:
        # First set known values.
        client.patch(
            "/settings",
            json={
                "gemini_answer_model": "initial-answer",
                "gemini_embedding_model": "initial-embedding",
                "cosine_threshold": 0.70,
                "cookie_secure_flag": True,
            },
            cookies={"session_id": self.session_id},
        )

        # Partial update: only cosine_threshold.
        resp = client.patch(
            "/settings",
            json={"cosine_threshold": 0.55},
            cookies={"session_id": self.session_id},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["cosine_threshold"] == 0.55
        # Untouched fields keep their previous values.
        assert body["gemini_answer_model"] == "initial-answer"
        assert body["gemini_embedding_model"] == "initial-embedding"
        assert body["cookie_secure_flag"] is True

    def test_patch_empty_body_keeps_all_defaults(self) -> None:
        resp = client.patch(
            "/settings",
            json={},
            cookies={"session_id": self.session_id},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["gemini_answer_model"] == "gemini-2.0-flash"
        assert body["gemini_embedding_model"] == "text-embedding-004"
        assert body["cosine_threshold"] == 0.75
        assert body["cookie_secure_flag"] is True


# ---------------------------------------------------------------------------
# AC-088 — updated cosine_threshold is read from DB at query time
# ---------------------------------------------------------------------------


class TestSettingsAccessorCosineThreshold:
    def setup_method(self) -> None:
        _cleanup_settings()

    def teardown_method(self) -> None:
        _cleanup_settings()

    def test_accessor_returns_default_then_updated_threshold(self) -> None:
        with SessionLocal() as db:
            settings = get_current_settings(db)
            assert settings.cosine_threshold == 0.75

        # Simulate a PATCH by writing directly to the DB (as the router does).
        with SessionLocal() as db:
            settings = get_current_settings(db)
            settings.cosine_threshold = 0.88
            db.commit()

        # At "query time" the accessor reads the new value from the DB.
        with SessionLocal() as db:
            settings = get_current_settings(db)
            assert settings.cosine_threshold == 0.88

    def test_accessor_threshold_reflects_api_patch(self) -> None:
        admin_email = "us031_accessor_admin@example.com"
        admin_pw = "admin-pw-123"
        _create_user(admin_email, admin_pw, role="Administrator")
        session_id = _login(admin_email, admin_pw)
        try:
            client.patch(
                "/settings",
                json={"cosine_threshold": 0.91},
                cookies={"session_id": session_id},
            )
            with SessionLocal() as db:
                settings = get_current_settings(db)
                assert settings.cosine_threshold == 0.91
        finally:
            _logout(session_id)
            _cleanup_settings()
            _delete_user(admin_email)


# ---------------------------------------------------------------------------
# AC-089 — updated Gemini model names are read from DB at query time
# ---------------------------------------------------------------------------


class TestSettingsAccessorModelNames:
    def setup_method(self) -> None:
        _cleanup_settings()

    def teardown_method(self) -> None:
        _cleanup_settings()

    def test_accessor_returns_default_then_updated_models(self) -> None:
        with SessionLocal() as db:
            settings = get_current_settings(db)
            assert settings.gemini_answer_model == "gemini-2.0-flash"
            assert settings.gemini_embedding_model == "text-embedding-004"

        with SessionLocal() as db:
            settings = get_current_settings(db)
            settings.gemini_answer_model = "gemini-1.5-ultra"
            settings.gemini_embedding_model = "text-embedding-006"
            db.commit()

        with SessionLocal() as db:
            settings = get_current_settings(db)
            assert settings.gemini_answer_model == "gemini-1.5-ultra"
            assert settings.gemini_embedding_model == "text-embedding-006"

    def test_accessor_models_reflect_api_patch(self) -> None:
        admin_email = "us031_model_admin@example.com"
        admin_pw = "admin-pw-123"
        _create_user(admin_email, admin_pw, role="Administrator")
        session_id = _login(admin_email, admin_pw)
        try:
            client.patch(
                "/settings",
                json={
                    "gemini_answer_model": "gemini-pro-1.5",
                    "gemini_embedding_model": "embed-v2",
                },
                cookies={"session_id": session_id},
            )
            with SessionLocal() as db:
                settings = get_current_settings(db)
                assert settings.gemini_answer_model == "gemini-pro-1.5"
                assert settings.gemini_embedding_model == "embed-v2"
        finally:
            _logout(session_id)
            _cleanup_settings()
            _delete_user(admin_email)


# ---------------------------------------------------------------------------
# AC-090 — regular user PATCH /settings → 403
# ---------------------------------------------------------------------------


class TestRegularUserPatchSettings:
    def setup_method(self) -> None:
        self.regular_email = "us031_regular_patch@example.com"
        self.pw = "pw-123"
        _create_user(self.regular_email, self.pw, role="Regular User")
        self.session_id = _login(self.regular_email, self.pw)
        _cleanup_settings()

    def teardown_method(self) -> None:
        _logout(self.session_id)
        _cleanup_settings()
        _delete_user(self.regular_email)

    def test_regular_user_patch_returns_403(self) -> None:
        resp = client.patch(
            "/settings",
            json={"cosine_threshold": 0.99},
            cookies={"session_id": self.session_id},
        )
        assert resp.status_code == 403

    def test_regular_user_patch_does_not_change_db(self) -> None:
        client.patch(
            "/settings",
            json={"cosine_threshold": 0.99},
            cookies={"session_id": self.session_id},
        )
        row = _get_settings_row()
        # No row should have been created/modified by a forbidden call.
        if row is not None:
            assert row.cosine_threshold == 0.75


# ---------------------------------------------------------------------------
# Unauthenticated access → 401
# ---------------------------------------------------------------------------


class TestUnauthenticatedSettings:
    def test_unauthenticated_get_returns_401(self) -> None:
        resp = client.get("/settings")
        assert resp.status_code == 401

    def test_unauthenticated_patch_returns_401(self) -> None:
        resp = client.patch("/settings", json={"cosine_threshold": 0.5})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# get_current_settings — unit-level behaviour
# ---------------------------------------------------------------------------


class TestGetCurrentSettings:
    def setup_method(self) -> None:
        _cleanup_settings()

    def teardown_method(self) -> None:
        _cleanup_settings()

    def test_creates_singleton_with_defaults_when_absent(self) -> None:
        assert _get_settings_row() is None
        with SessionLocal() as db:
            settings = get_current_settings(db)
            assert settings.id == 1
            assert settings.gemini_answer_model == "gemini-2.0-flash"
            assert settings.gemini_embedding_model == "text-embedding-004"
            assert settings.cosine_threshold == 0.75
            assert settings.cookie_secure_flag is True

    def test_returns_existing_row_without_overwriting(self) -> None:
        with SessionLocal() as db:
            settings = get_current_settings(db)
            settings.cosine_threshold = 0.42
            settings.gemini_answer_model = "custom-model"
            db.commit()

        with SessionLocal() as db:
            settings = get_current_settings(db)
            assert settings.cosine_threshold == 0.42
            assert settings.gemini_answer_model == "custom-model"
