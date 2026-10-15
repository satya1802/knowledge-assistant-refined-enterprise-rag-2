"""Integration tests for GET /settings and PATCH /settings (US-031-3).

Covers:
  AC-085 — admin GET /settings returns 200 with gemini_answer_model,
           gemini_embedding_model, cosine_threshold, cookie_secure_flag.
  AC-086 — regular user GET /settings → 403 Forbidden.
  AC-087 — admin PATCH /settings with updated values → 200, values persisted
           to DB, updated values returned.
  AC-087b — PATCH persists across a new SessionLocal (simulated restart).
  AC-088 — get_current_settings accessor returns the live DB values after PATCH.
  AC-090 — regular user PATCH /settings → 403 Forbidden.
  AC-091 — partial PATCH (only cosine_threshold) updates only that field,
           others unchanged.
  AC-092 — unauthenticated GET /settings → 401 Unauthorized.

Follows patterns from test_auth_login.py: TestClient, direct DB inserts for
fixtures, login to obtain session cookies, try/finally cleanup.
"""

from __future__ import annotations

import bcrypt
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import SessionLocal
from app.main import app
from app.models import Settings, User
from app.services import get_current_settings

client = TestClient(app)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hash(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _create_user(email: str, password: str, role: str = "User") -> User:
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


def _cleanup_settings() -> None:
    """Delete the singleton Settings row so each test starts fresh."""
    with SessionLocal() as db:
        settings = db.execute(select(Settings).where(Settings.id == 1)).scalar_one_or_none()
        if settings is not None:
            db.delete(settings)
        db.commit()


def _get_settings_row() -> Settings | None:
    """Return the raw Settings row from the DB (or None)."""
    with SessionLocal() as db:
        return db.execute(select(Settings).where(Settings.id == 1)).scalar_one_or_none()


# ---------------------------------------------------------------------------
# AC-085 — admin GET /settings → 200, returns all four fields
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

    def test_admin_get_returns_200(self) -> None:
        resp = client.get("/settings", cookies={"session_id": self.session_id})
        assert resp.status_code == 200, resp.text

    def test_admin_get_returns_all_four_fields(self) -> None:
        resp = client.get("/settings", cookies={"session_id": self.session_id})
        assert resp.status_code == 200
        body = resp.json()
        assert "gemini_answer_model" in body
        assert "gemini_embedding_model" in body
        assert "cosine_threshold" in body
        assert "cookie_secure_flag" in body

    def test_admin_get_returns_default_values(self) -> None:
        """When the singleton row doesn't yet exist, GET returns model defaults."""
        assert _get_settings_row() is None
        resp = client.get("/settings", cookies={"session_id": self.session_id})
        assert resp.status_code == 200
        body = resp.json()
        assert body["gemini_answer_model"] == "gemini-2.0-flash"
        assert body["gemini_embedding_model"] == "text-embedding-004"
        assert body["cosine_threshold"] == 0.75
        assert body["cookie_secure_flag"] is True


# ---------------------------------------------------------------------------
# AC-086 — regular user GET /settings → 403 Forbidden
# ---------------------------------------------------------------------------


class TestRegularUserGetSettings:
    def setup_method(self) -> None:
        self.regular_email = "us031_regular_get@example.com"
        self.pw = "pw-123"
        _create_user(self.regular_email, self.pw, role="User")
        self.session_id = _login(self.regular_email, self.pw)

    def teardown_method(self) -> None:
        _logout(self.session_id)
        _delete_user(self.regular_email)

    def test_regular_user_get_returns_403(self) -> None:
        resp = client.get("/settings", cookies={"session_id": self.session_id})
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# AC-092 — unauthenticated GET /settings → 401
# ---------------------------------------------------------------------------


class TestUnauthenticatedGetSettings:
    def test_unauthenticated_get_returns_401(self) -> None:
        resp = client.get("/settings")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# AC-087 — admin PATCH /settings → 200, values in DB, updated values returned
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

    def test_patch_returns_200_with_updated_values(self) -> None:
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

    def test_patch_persists_values_to_db(self) -> None:
        """The updated values must be committed to the database."""
        client.patch(
            "/settings",
            json={
                "gemini_answer_model": "gemini-1.5-flash",
                "gemini_embedding_model": "text-embedding-003",
                "cosine_threshold": 0.68,
                "cookie_secure_flag": False,
            },
            cookies={"session_id": self.session_id},
        )
        row = _get_settings_row()
        assert row is not None
        assert row.gemini_answer_model == "gemini-1.5-flash"
        assert row.gemini_embedding_model == "text-embedding-003"
        assert row.cosine_threshold == 0.68
        assert row.cookie_secure_flag is False


# ---------------------------------------------------------------------------
# AC-087b — PATCH persists across a new SessionLocal (simulated restart)
# ---------------------------------------------------------------------------


class TestPatchPersistsAcrossRestart:
    def setup_method(self) -> None:
        self.admin_email = "us031_restart_admin@example.com"
        self.admin_pw = "admin-pw-123"
        _create_user(self.admin_email, self.admin_pw, role="Administrator")
        self.session_id = _login(self.admin_email, self.admin_pw)
        _cleanup_settings()

    def teardown_method(self) -> None:
        _logout(self.session_id)
        _cleanup_settings()
        _delete_user(self.admin_email)

    def test_patched_values_read_from_new_session(self) -> None:
        """A fresh SessionLocal() — simulating a restart — reads the updated values."""
        client.patch(
            "/settings",
            json={
                "gemini_answer_model": "gemini-pro-restart",
                "gemini_embedding_model": "embed-restart",
                "cosine_threshold": 0.91,
                "cookie_secure_flag": True,
            },
            cookies={"session_id": self.session_id},
        )
        with SessionLocal() as db:
            settings = get_current_settings(db)
            assert settings.gemini_answer_model == "gemini-pro-restart"
            assert settings.gemini_embedding_model == "embed-restart"
            assert settings.cosine_threshold == 0.91
            assert settings.cookie_secure_flag is True


# ---------------------------------------------------------------------------
# AC-090 — regular user PATCH /settings → 403
# ---------------------------------------------------------------------------


class TestRegularUserPatchSettings:
    def setup_method(self) -> None:
        self.regular_email = "us031_regular_patch@example.com"
        self.pw = "pw-123"
        _create_user(self.regular_email, self.pw, role="User")
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
        """A forbidden PATCH must not alter the database."""
        # Ensure a row exists with default values.
        with SessionLocal() as db:
            get_current_settings(db)  # creates singleton with defaults

        client.patch(
            "/settings",
            json={"cosine_threshold": 0.99},
            cookies={"session_id": self.session_id},
        )
        row = _get_settings_row()
        assert row is not None
        assert row.cosine_threshold == 0.75


# ---------------------------------------------------------------------------
# AC-091 — partial PATCH (only cosine_threshold) updates only that field
# ---------------------------------------------------------------------------


class TestPartialPatchSettings:
    def setup_method(self) -> None:
        self.admin_email = "us031_partial_admin@example.com"
        self.admin_pw = "admin-pw-123"
        _create_user(self.admin_email, self.admin_pw, role="Administrator")
        self.session_id = _login(self.admin_email, self.admin_pw)
        _cleanup_settings()

    def teardown_method(self) -> None:
        _logout(self.session_id)
        _cleanup_settings()
        _delete_user(self.admin_email)

    def test_partial_patch_updates_only_cosine_threshold(self) -> None:
        # Set known initial values via a full PATCH.
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
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["cosine_threshold"] == 0.55
        # Untouched fields must retain their previous values.
        assert body["gemini_answer_model"] == "initial-answer"
        assert body["gemini_embedding_model"] == "initial-embedding"
        assert body["cookie_secure_flag"] is True

    def test_partial_patch_db_reflects_only_changed_field(self) -> None:
        client.patch(
            "/settings",
            json={
                "gemini_answer_model": "keep-answer",
                "gemini_embedding_model": "keep-embedding",
                "cosine_threshold": 0.60,
                "cookie_secure_flag": False,
            },
            cookies={"session_id": self.session_id},
        )
        client.patch(
            "/settings",
            json={"cosine_threshold": 0.33},
            cookies={"session_id": self.session_id},
        )
        row = _get_settings_row()
        assert row is not None
        assert row.cosine_threshold == 0.33
        assert row.gemini_answer_model == "keep-answer"
        assert row.gemini_embedding_model == "keep-embedding"
        assert row.cookie_secure_flag is False


# ---------------------------------------------------------------------------
# AC-088 — get_current_settings accessor returns live DB values after PATCH
# ---------------------------------------------------------------------------


class TestSettingsAccessor:
    def setup_method(self) -> None:
        self.admin_email = "us031_accessor_admin@example.com"
        self.admin_pw = "admin-pw-123"
        _create_user(self.admin_email, self.admin_pw, role="Administrator")
        self.session_id = _login(self.admin_email, self.admin_pw)
        _cleanup_settings()

    def teardown_method(self) -> None:
        _logout(self.session_id)
        _cleanup_settings()
        _delete_user(self.admin_email)

    def test_accessor_returns_defaults_before_patch(self) -> None:
        with SessionLocal() as db:
            settings = get_current_settings(db)
            assert settings.gemini_answer_model == "gemini-2.0-flash"
            assert settings.gemini_embedding_model == "text-embedding-004"
            assert settings.cosine_threshold == 0.75
            assert settings.cookie_secure_flag is True

    def test_accessor_returns_updated_values_after_patch(self) -> None:
        client.patch(
            "/settings",
            json={
                "gemini_answer_model": "accessor-answer",
                "gemini_embedding_model": "accessor-embedding",
                "cosine_threshold": 0.88,
                "cookie_secure_flag": False,
            },
            cookies={"session_id": self.session_id},
        )
        with SessionLocal() as db:
            settings = get_current_settings(db)
            assert settings.gemini_answer_model == "accessor-answer"
            assert settings.gemini_embedding_model == "accessor-embedding"
            assert settings.cosine_threshold == 0.88
            assert settings.cookie_secure_flag is False

    def test_accessor_reads_live_values_from_new_session(self) -> None:
        """get_current_settings must read from the DB at query time — not a cache."""
        client.patch(
            "/settings",
            json={"cosine_threshold": 0.77},
            cookies={"session_id": self.session_id},
        )
        # A brand-new session simulates a fresh request cycle.
        with SessionLocal() as db:
            settings = get_current_settings(db)
            assert settings.cosine_threshold == 0.77