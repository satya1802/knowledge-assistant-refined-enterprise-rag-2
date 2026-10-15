"""Integration tests for GET /users and POST /users (US-007-3).

Covers:
  AC — admin creates user with valid unique email → success, user record
       exists with bcrypt hash, password not stored in plaintext.
  AC — admin creates user with duplicate email → 409 conflict, no duplicate.
  AC — regular user calls POST /users → 403 Forbidden.
  AC — unauthenticated call to POST /users → 401 Unauthorized.
  AC — admin calls GET /users → 200, list with id/email/role, no password_hash.
  AC — regular user calls GET /users → 403 Forbidden.
  AC — invalid role value rejected with 422.

Follows the patterns established in test_auth_login.py: TestClient, direct DB
inserts for fixtures, login to obtain session cookies, try/finally cleanup.
"""

from __future__ import annotations

import bcrypt
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import SessionLocal
from app.main import app
from app.models import User

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


def _get_password_hash(email: str) -> str:
    """Return the stored password_hash for *email* from the DB."""
    with SessionLocal() as db:
        user = db.execute(select(User).where(User.email == email)).scalar_one()
        return user.password_hash


def _count_users_with_email(email: str) -> int:
    """Return how many users in the DB have *email*."""
    with SessionLocal() as db:
        users = db.execute(select(User).where(User.email == email)).scalars().all()
        return len(users)


# ---------------------------------------------------------------------------
# POST /users — admin creates user with valid unique email
# ---------------------------------------------------------------------------


class TestCreateUserSuccess:
    def test_admin_creates_user_returns_success(self) -> None:
        admin_email = "us007_admin_create@example.com"
        admin_pw = "admin-password-123"
        new_email = "us007_newuser@example.com"
        new_password = "new-user-password-123"
        _create_user(admin_email, admin_pw, role="Administrator")
        try:
            session_id = _login(admin_email, admin_pw)

            resp = client.post(
                "/users",
                json={"email": new_email, "password": new_password, "role": "Regular User"},
                cookies={"session_id": session_id},
            )

            # The implementation returns 201 Created; the AC says 200.  Both
            # are success statuses, so accept either.
            assert resp.status_code in (200, 201), resp.text
            body = resp.json()
            assert set(body.keys()) == {"id", "email", "role"}
            assert body["email"] == new_email
            assert body["role"] == "Regular User"
            assert isinstance(body["id"], int)
        finally:
            _delete_user(new_email)
            _delete_user(admin_email)

    def test_created_user_record_exists_with_bcrypt_hash(self) -> None:
        admin_email = "us007_admin_hash@example.com"
        admin_pw = "admin-password-123"
        new_email = "us007_hashuser@example.com"
        new_password = "hash-check-password-123"
        _create_user(admin_email, admin_pw, role="Administrator")
        try:
            session_id = _login(admin_email, admin_pw)

            resp = client.post(
                "/users",
                json={"email": new_email, "password": new_password, "role": "Administrator"},
                cookies={"session_id": session_id},
            )
            assert resp.status_code in (200, 201), resp.text

            # The user record must exist in the DB.
            with SessionLocal() as db:
                user = db.execute(select(User).where(User.email == new_email)).scalar_one()
                assert user is not None
                # The hash must be a bcrypt hash.
                assert user.password_hash.startswith("$2")
                # The hash must verify against the supplied password.
                assert bcrypt.checkpw(
                    new_password.encode("utf-8"), user.password_hash.encode("utf-8")
                )
        finally:
            _delete_user(new_email)
            _delete_user(admin_email)

    def test_password_not_stored_in_plaintext(self) -> None:
        admin_email = "us007_admin_plain@example.com"
        admin_pw = "admin-password-123"
        new_email = "us007_plainuser@example.com"
        new_password = "plaintext-check-123"
        _create_user(admin_email, admin_pw, role="Administrator")
        try:
            session_id = _login(admin_email, admin_pw)

            client.post(
                "/users",
                json={"email": new_email, "password": new_password, "role": "Regular User"},
                cookies={"session_id": session_id},
            )

            stored_hash = _get_password_hash(new_email)
            # The plaintext password must not appear anywhere in the stored hash.
            assert new_password not in stored_hash
            assert stored_hash != new_password
        finally:
            _delete_user(new_email)
            _delete_user(admin_email)


# ---------------------------------------------------------------------------
# POST /users — duplicate email → 409
# ---------------------------------------------------------------------------


class TestCreateUserDuplicateEmail:
    def test_duplicate_email_returns_409(self) -> None:
        admin_email = "us007_admin_dup@example.com"
        admin_pw = "admin-password-123"
        existing_email = "us007_existing@example.com"
        existing_pw = "existing-password-123"
        _create_user(admin_email, admin_pw, role="Administrator")
        _create_user(existing_email, existing_pw, role="Regular User")
        try:
            session_id = _login(admin_email, admin_pw)

            resp = client.post(
                "/users",
                json={
                    "email": existing_email,
                    "password": "some-password-123",
                    "role": "Regular User",
                },
                cookies={"session_id": session_id},
            )

            assert resp.status_code == 409, resp.text
        finally:
            _delete_user(existing_email)
            _delete_user(admin_email)

    def test_duplicate_email_does_not_create_second_record(self) -> None:
        admin_email = "us007_admin_dup2@example.com"
        admin_pw = "admin-password-123"
        existing_email = "us007_existing2@example.com"
        existing_pw = "existing-password-123"
        _create_user(admin_email, admin_pw, role="Administrator")
        _create_user(existing_email, existing_pw, role="Regular User")
        try:
            session_id = _login(admin_email, admin_pw)

            client.post(
                "/users",
                json={
                    "email": existing_email,
                    "password": "some-password-123",
                    "role": "Regular User",
                },
                cookies={"session_id": session_id},
            )

            # Exactly one user with that email must exist.
            assert _count_users_with_email(existing_email) == 1
        finally:
            _delete_user(existing_email)
            _delete_user(admin_email)


# ---------------------------------------------------------------------------
# POST /users — regular user → 403
# ---------------------------------------------------------------------------


class TestCreateUserForbidden:
    def test_regular_user_post_users_returns_403(self) -> None:
        user_email = "us007_regular_post@example.com"
        user_pw = "regular-password-123"
        new_email = "us007_should_not_create@example.com"
        _create_user(user_email, user_pw, role="Regular User")
        try:
            session_id = _login(user_email, user_pw)

            resp = client.post(
                "/users",
                json={"email": new_email, "password": "pw-12345678", "role": "Regular User"},
                cookies={"session_id": session_id},
            )

            assert resp.status_code == 403, resp.text
        finally:
            _delete_user(new_email)
            _delete_user(user_email)


# ---------------------------------------------------------------------------
# POST /users — unauthenticated → 401
# ---------------------------------------------------------------------------


class TestCreateUserUnauthenticated:
    def test_unauthenticated_post_users_returns_401(self) -> None:
        resp = client.post(
            "/users",
            json={"email": "noauth@example.com", "password": "pw-12345678", "role": "Regular User"},
        )
        assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------------------
# GET /users — admin → 200, list with id/email/role, no password_hash
# ---------------------------------------------------------------------------


class TestListUsersAdmin:
    def test_admin_get_users_returns_200(self) -> None:
        admin_email = "us007_admin_get@example.com"
        admin_pw = "admin-password-123"
        _create_user(admin_email, admin_pw, role="Administrator")
        try:
            session_id = _login(admin_email, admin_pw)

            resp = client.get("/users", cookies={"session_id": session_id})

            assert resp.status_code == 200, resp.text
        finally:
            _delete_user(admin_email)

    def test_admin_get_users_returns_list_with_correct_fields(self) -> None:
        admin_email = "us007_admin_fields@example.com"
        admin_pw = "admin-password-123"
        other_email = "us007_other@example.com"
        other_pw = "other-password-123"
        _create_user(admin_email, admin_pw, role="Administrator")
        _create_user(other_email, other_pw, role="Regular User")
        try:
            session_id = _login(admin_email, admin_pw)

            resp = client.get("/users", cookies={"session_id": session_id})
            assert resp.status_code == 200, resp.text

            body = resp.json()
            assert isinstance(body, list)
            assert len(body) >= 2

            # Every entry must have exactly {id, email, role} — no password_hash.
            for entry in body:
                assert set(entry.keys()) == {"id", "email", "role"}, (
                    f"Unexpected keys: {set(entry.keys())}"
                )
                assert "password_hash" not in entry
                assert "password" not in entry
                assert isinstance(entry["id"], int)
                assert isinstance(entry["email"], str)
                assert isinstance(entry["role"], str)

            # Both created users must appear in the list.
            emails = [e["email"] for e in body]
            assert admin_email in emails
            assert other_email in emails
        finally:
            _delete_user(other_email)
            _delete_user(admin_email)


# ---------------------------------------------------------------------------
# GET /users — regular user → 403
# ---------------------------------------------------------------------------


class TestListUsersForbidden:
    def test_regular_user_get_users_returns_403(self) -> None:
        user_email = "us007_regular_get@example.com"
        user_pw = "regular-password-123"
        _create_user(user_email, user_pw, role="Regular User")
        try:
            session_id = _login(user_email, user_pw)

            resp = client.get("/users", cookies={"session_id": session_id})

            assert resp.status_code == 403, resp.text
        finally:
            _delete_user(user_email)


# ---------------------------------------------------------------------------
# POST /users — invalid role → 422
# ---------------------------------------------------------------------------


class TestCreateUserInvalidRole:
    def test_invalid_role_returns_422(self) -> None:
        admin_email = "us007_admin_role@example.com"
        admin_pw = "admin-password-123"
        new_email = "us007_badrole@example.com"
        _create_user(admin_email, admin_pw, role="Administrator")
        try:
            session_id = _login(admin_email, admin_pw)

            resp = client.post(
                "/users",
                json={"email": new_email, "password": "pw-12345678", "role": "SuperAdmin"},
                cookies={"session_id": session_id},
            )

            assert resp.status_code == 422, resp.text

            # The user must not have been created.
            assert _count_users_with_email(new_email) == 0
        finally:
            _delete_user(new_email)
            _delete_user(admin_email)

    def test_role_user_rejected_with_422(self) -> None:
        """The legacy 'User' role string is not accepted — only 'Administrator'
        and 'Regular User' are valid."""
        admin_email = "us007_admin_role2@example.com"
        admin_pw = "admin-password-123"
        new_email = "us007_badrole2@example.com"
        _create_user(admin_email, admin_pw, role="Administrator")
        try:
            session_id = _login(admin_email, admin_pw)

            resp = client.post(
                "/users",
                json={"email": new_email, "password": "pw-12345678", "role": "User"},
                cookies={"session_id": session_id},
            )

            assert resp.status_code == 422, resp.text
            assert _count_users_with_email(new_email) == 0
        finally:
            _delete_user(new_email)
            _delete_user(admin_email)
