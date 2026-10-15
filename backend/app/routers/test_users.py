"""Integration tests for GET /users and POST /users (US-007-1).

These tests live inside ``backend/app/routers/`` because the task scope
restricts writes to that directory.  They replicate the test-database
bootstrap that ``backend/tests/conftest.py`` performs so they can run
standalone with ``pytest backend/app/routers/test_users.py``.

Covers:
  AC-015 — admin creates a user with a unique email; bcrypt hash stored,
           success response returned.
  AC-016 — admin creates a user with an existing email → 409, no duplicate.
  AC-017 — non-admin user calls POST /users → 403.
  AC-018 — unauthenticated POST /users → 401 (no public signup endpoint).
  AC-019 — admin GET /users returns all users with id, email, role only;
           password hashes never included.
  AC-020 — non-admin user calls GET /users → 403.
  Contract — invalid role → 422.
"""

from __future__ import annotations

import os
from pathlib import Path

# Point at a throwaway database and remove any pre-existing files BEFORE
# importing the application (which creates tables at import time).
os.environ["DATABASE_URL"] = "sqlite:///./test_users_router.db"
for _name in ("app.db", "test_users_router.db"):
    _p = Path(_name)
    if _p.exists():
        _p.unlink()

import bcrypt  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402

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
    """Log out to invalidate the session."""
    client.post("/auth/logout", cookies={"session_id": session_id})


# ---------------------------------------------------------------------------
# AC-015 — admin creates a user with a unique email
# ---------------------------------------------------------------------------


class TestCreateUserSuccess:
    def test_admin_creates_user_with_unique_email(self) -> None:
        admin_email = "ac015_admin@example.com"
        new_email = "ac015_new@example.com"
        admin_pw = "admin-pw-123"
        new_pw = "new-user-pw-123"
        _create_user(admin_email, admin_pw, role="Administrator")
        try:
            session_id = _login(admin_email, admin_pw)
            resp = client.post(
                "/users",
                json={"email": new_email, "password": new_pw, "role": "Regular User"},
                cookies={"session_id": session_id},
            )

            assert resp.status_code == 201
            body = resp.json()
            assert set(body.keys()) == {"id", "email", "role"}
            assert body["email"] == new_email
            assert body["role"] == "Regular User"
            assert isinstance(body["id"], int)
        finally:
            _logout(session_id)
            _delete_user(new_email)
            _delete_user(admin_email)

    def test_bcrypt_hash_stored_not_plaintext(self) -> None:
        admin_email = "ac015_hash_admin@example.com"
        new_email = "ac015_hash_new@example.com"
        admin_pw = "admin-pw-123"
        new_pw = "plaintext-secret"
        _create_user(admin_email, admin_pw, role="Administrator")
        try:
            session_id = _login(admin_email, admin_pw)
            client.post(
                "/users",
                json={"email": new_email, "password": new_pw, "role": "Regular User"},
                cookies={"session_id": session_id},
            )

            with SessionLocal() as db:
                user = db.execute(
                    select(User).where(User.email == new_email)
                ).scalar_one()
                # Stored hash must not be the plaintext.
                assert user.password_hash != new_pw
                # Must be a valid bcrypt hash verifiable against the plaintext.
                assert bcrypt.checkpw(
                    new_pw.encode("utf-8"), user.password_hash.encode("utf-8")
                )
        finally:
            _logout(session_id)
            _delete_user(new_email)
            _delete_user(admin_email)

    def test_admin_can_create_administrator_role(self) -> None:
        admin_email = "ac015_role_admin@example.com"
        new_email = "ac015_role_new@example.com"
        admin_pw = "admin-pw-123"
        _create_user(admin_email, admin_pw, role="Administrator")
        try:
            session_id = _login(admin_email, admin_pw)
            resp = client.post(
                "/users",
                json={"email": new_email, "password": "pw-123", "role": "Administrator"},
                cookies={"session_id": session_id},
            )

            assert resp.status_code == 201
            assert resp.json()["role"] == "Administrator"
        finally:
            _logout(session_id)
            _delete_user(new_email)
            _delete_user(admin_email)


# ---------------------------------------------------------------------------
# AC-016 — duplicate email → 409, no duplicate created
# ---------------------------------------------------------------------------


class TestCreateUserDuplicate:
    def test_duplicate_email_returns_409(self) -> None:
        admin_email = "ac016_admin@example.com"
        dup_email = "ac016_dup@example.com"
        admin_pw = "admin-pw-123"
        _create_user(admin_email, admin_pw, role="Administrator")
        _create_user(dup_email, "existing-pw", role="Regular User")
        try:
            session_id = _login(admin_email, admin_pw)
            resp = client.post(
                "/users",
                json={"email": dup_email, "password": "new-pw", "role": "Regular User"},
                cookies={"session_id": session_id},
            )

            assert resp.status_code == 409
        finally:
            _logout(session_id)
            _delete_user(dup_email)
            _delete_user(admin_email)

    def test_duplicate_email_creates_no_second_record(self) -> None:
        admin_email = "ac016_nodup_admin@example.com"
        dup_email = "ac016_nodup@example.com"
        admin_pw = "admin-pw-123"
        _create_user(admin_email, admin_pw, role="Administrator")
        _create_user(dup_email, "existing-pw", role="Regular User")
        try:
            session_id = _login(admin_email, admin_pw)
            client.post(
                "/users",
                json={"email": dup_email, "password": "new-pw", "role": "Regular User"},
                cookies={"session_id": session_id},
            )

            with SessionLocal() as db:
                users = (
                    db.execute(select(User).where(User.email == dup_email))
                    .scalars()
                    .all()
                )
                assert len(users) == 1
        finally:
            _logout(session_id)
            _delete_user(dup_email)
            _delete_user(admin_email)


# ---------------------------------------------------------------------------
# AC-017 — non-admin POST /users → 403
# ---------------------------------------------------------------------------


class TestCreateUserForbidden:
    def test_non_admin_gets_403(self) -> None:
        regular_email = "ac017_regular@example.com"
        new_email = "ac017_new@example.com"
        regular_pw = "regular-pw-123"
        _create_user(regular_email, regular_pw, role="Regular User")
        try:
            session_id = _login(regular_email, regular_pw)
            resp = client.post(
                "/users",
                json={"email": new_email, "password": "pw-123", "role": "Regular User"},
                cookies={"session_id": session_id},
            )

            assert resp.status_code == 403
        finally:
            _logout(session_id)
            _delete_user(regular_email)

    def test_non_admin_post_creates_no_user(self) -> None:
        regular_email = "ac017_nocreate@example.com"
        new_email = "ac017_nocreate_new@example.com"
        regular_pw = "regular-pw-123"
        _create_user(regular_email, regular_pw, role="Regular User")
        try:
            session_id = _login(regular_email, regular_pw)
            client.post(
                "/users",
                json={"email": new_email, "password": "pw-123", "role": "Regular User"},
                cookies={"session_id": session_id},
            )

            with SessionLocal() as db:
                user = (
                    db.execute(select(User).where(User.email == new_email))
                    .scalar_one_or_none()
                )
                assert user is None
        finally:
            _logout(session_id)
            _delete_user(regular_email)


# ---------------------------------------------------------------------------
# AC-018 — unauthenticated POST /users → 401; no public signup endpoint
# ---------------------------------------------------------------------------


class TestCreateUserUnauthenticated:
    def test_no_cookie_returns_401(self) -> None:
        resp = client.post(
            "/users",
            json={
                "email": "ac018_noauth@example.com",
                "password": "pw-123",
                "role": "Regular User",
            },
        )
        assert resp.status_code == 401

    def test_invalid_session_returns_401(self) -> None:
        resp = client.post(
            "/users",
            json={
                "email": "ac018_bad@example.com",
                "password": "pw-123",
                "role": "Regular User",
            },
            cookies={"session_id": "not-a-uuid"},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# AC-019 — admin GET /users returns all users, id/email/role only
# ---------------------------------------------------------------------------


class TestListUsers:
    def test_admin_gets_all_users(self) -> None:
        admin_email = "ac019_admin@example.com"
        other_email = "ac019_other@example.com"
        admin_pw = "admin-pw-123"
        _create_user(admin_email, admin_pw, role="Administrator")
        _create_user(other_email, "other-pw", role="Regular User")
        try:
            session_id = _login(admin_email, admin_pw)
            resp = client.get("/users", cookies={"session_id": session_id})

            assert resp.status_code == 200
            users = resp.json()
            assert isinstance(users, list)
            emails = {u["email"] for u in users}
            assert admin_email in emails
            assert other_email in emails
        finally:
            _logout(session_id)
            _delete_user(other_email)
            _delete_user(admin_email)

    def test_list_users_has_only_id_email_role(self) -> None:
        admin_email = "ac019_keys_admin@example.com"
        admin_pw = "admin-pw-123"
        _create_user(admin_email, admin_pw, role="Administrator")
        try:
            session_id = _login(admin_email, admin_pw)
            resp = client.get("/users", cookies={"session_id": session_id})

            assert resp.status_code == 200
            for u in resp.json():
                assert set(u.keys()) == {"id", "email", "role"}
        finally:
            _logout(session_id)
            _delete_user(admin_email)

    def test_password_hashes_never_in_response(self) -> None:
        admin_email = "ac019_nohash_admin@example.com"
        other_email = "ac019_nohash_other@example.com"
        admin_pw = "admin-pw-123"
        _create_user(admin_email, admin_pw, role="Administrator")
        _create_user(other_email, "other-pw", role="Regular User")
        try:
            session_id = _login(admin_email, admin_pw)
            resp = client.get("/users", cookies={"session_id": session_id})

            assert resp.status_code == 200
            # Ensure the actual bcrypt hash prefix never leaks.
            with SessionLocal() as db:
                other = db.execute(
                    select(User).where(User.email == other_email)
                ).scalar_one()
                assert other.password_hash not in resp.text
        finally:
            _logout(session_id)
            _delete_user(other_email)
            _delete_user(admin_email)


# ---------------------------------------------------------------------------
# AC-020 — non-admin GET /users → 403
# ---------------------------------------------------------------------------


class TestListUsersForbidden:
    def test_non_admin_gets_403(self) -> None:
        regular_email = "ac020_regular@example.com"
        regular_pw = "regular-pw-123"
        _create_user(regular_email, regular_pw, role="Regular User")
        try:
            session_id = _login(regular_email, regular_pw)
            resp = client.get("/users", cookies={"session_id": session_id})

            assert resp.status_code == 403
        finally:
            _logout(session_id)
            _delete_user(regular_email)


# ---------------------------------------------------------------------------
# Contract — invalid role → 422
# ---------------------------------------------------------------------------


class TestCreateUserInvalidRole:
    def test_invalid_role_returns_422(self) -> None:
        admin_email = "ac422_admin@example.com"
        new_email = "ac422_new@example.com"
        admin_pw = "admin-pw-123"
        _create_user(admin_email, admin_pw, role="Administrator")
        try:
            session_id = _login(admin_email, admin_pw)
            resp = client.post(
                "/users",
                json={"email": new_email, "password": "pw-123", "role": "SuperUser"},
                cookies={"session_id": session_id},
            )

            assert resp.status_code == 422
        finally:
            _logout(session_id)
            _delete_user(new_email)
            _delete_user(admin_email)

    def test_invalid_role_creates_no_user(self) -> None:
        admin_email = "ac422_nocreate_admin@example.com"
        new_email = "ac422_nocreate_new@example.com"
        admin_pw = "admin-pw-123"
        _create_user(admin_email, admin_pw, role="Administrator")
        try:
            session_id = _login(admin_email, admin_pw)
            client.post(
                "/users",
                json={"email": new_email, "password": "pw-123", "role": "Manager"},
                cookies={"session_id": session_id},
            )

            with SessionLocal() as db:
                user = (
                    db.execute(select(User).where(User.email == new_email))
                    .scalar_one_or_none()
                )
                assert user is None
        finally:
            _logout(session_id)
            _delete_user(admin_email)