"""Integration tests for POST /auth/change-password (US-006-1).

Covers:
  AC-013 — with a valid session, submitting the correct current password and
           a new password replaces the stored hash (new hash verifies against
           the new password, not the old) and returns success.
  AC-014 — with a valid session, submitting an incorrect current password
           does not change the stored hash and returns an error indicating the
           current password is incorrect.
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


def _get_password_hash(email: str) -> str:
    """Return the current stored password hash for *email*."""
    with SessionLocal() as db:
        user = db.execute(select(User).where(User.email == email)).scalar_one()
        return user.password_hash


# ---------------------------------------------------------------------------
# AC-013 — correct current password + new password → hash replaced, success
# ---------------------------------------------------------------------------


class TestChangePasswordSuccess:
    def test_change_password_returns_success(self) -> None:
        email = "ac013_success@example.com"
        old_password = "old-password-123"
        new_password = "new-password-456"
        _create_user(email, old_password)
        try:
            session_id = _login(email, old_password)

            resp = client.post(
                "/auth/change-password",
                json={"current_password": old_password, "new_password": new_password},
                cookies={"session_id": session_id},
            )

            assert resp.status_code in (200, 204), resp.text
            if resp.status_code == 200:
                assert "message" in resp.json()
        finally:
            _delete_user(email)

    def test_change_password_replaces_stored_hash(self) -> None:
        """The stored hash must verify against the new password, not the old."""
        email = "ac013_replace@example.com"
        old_password = "old-password-123"
        new_password = "new-password-456"
        _create_user(email, old_password)
        try:
            session_id = _login(email, old_password)

            old_hash = _get_password_hash(email)

            resp = client.post(
                "/auth/change-password",
                json={"current_password": old_password, "new_password": new_password},
                cookies={"session_id": session_id},
            )
            assert resp.status_code in (200, 204), resp.text

            new_hash = _get_password_hash(email)

            # The hash must have changed.
            assert new_hash != old_hash

            # The new hash verifies against the new password.
            assert bcrypt.checkpw(new_password.encode("utf-8"), new_hash.encode("utf-8"))

            # The new hash does NOT verify against the old password.
            assert not bcrypt.checkpw(old_password.encode("utf-8"), new_hash.encode("utf-8"))
        finally:
            _delete_user(email)

    def test_can_login_with_new_password_after_change(self) -> None:
        """After changing the password, the user can log in with the new one
        and the old one no longer works."""
        email = "ac013_relogin@example.com"
        old_password = "old-password-123"
        new_password = "new-password-456"
        _create_user(email, old_password)
        try:
            session_id = _login(email, old_password)

            resp = client.post(
                "/auth/change-password",
                json={"current_password": old_password, "new_password": new_password},
                cookies={"session_id": session_id},
            )
            assert resp.status_code in (200, 204), resp.text

            # Old password no longer works.
            old_resp = client.post("/auth/login", json={"email": email, "password": old_password})
            assert old_resp.status_code == 401

            # New password works.
            new_resp = client.post("/auth/login", json={"email": email, "password": new_password})
            assert new_resp.status_code == 200
        finally:
            _delete_user(email)

    def test_change_password_requires_session(self) -> None:
        """Without a session cookie, change-password returns 401."""
        email = "ac013_nosession@example.com"
        old_password = "old-password-123"
        new_password = "new-password-456"
        _create_user(email, old_password)
        try:
            resp = client.post(
                "/auth/change-password",
                json={"current_password": old_password, "new_password": new_password},
            )
            assert resp.status_code == 401
        finally:
            _delete_user(email)


# ---------------------------------------------------------------------------
# AC-014 — incorrect current password → hash unchanged, error returned
# ---------------------------------------------------------------------------


class TestChangePasswordWrongCurrent:
    def test_wrong_current_password_returns_error(self) -> None:
        email = "ac014_wrong@example.com"
        old_password = "old-password-123"
        new_password = "new-password-456"
        _create_user(email, old_password)
        try:
            session_id = _login(email, old_password)

            resp = client.post(
                "/auth/change-password",
                json={"current_password": "totally-wrong", "new_password": new_password},
                cookies={"session_id": session_id},
            )

            # Must be an error status (400 or 401 — either is acceptable as
            # long as it indicates the current password is incorrect).
            assert resp.status_code >= 400, resp.text
            assert resp.status_code != 501, "Endpoint is not implemented (501 stub)"
        finally:
            _delete_user(email)

    def test_wrong_current_password_does_not_change_hash(self) -> None:
        """The stored hash must remain unchanged when the current password
        is incorrect."""
        email = "ac014_unchanged@example.com"
        old_password = "old-password-123"
        new_password = "new-password-456"
        _create_user(email, old_password)
        try:
            session_id = _login(email, old_password)

            old_hash = _get_password_hash(email)

            resp = client.post(
                "/auth/change-password",
                json={"current_password": "totally-wrong", "new_password": new_password},
                cookies={"session_id": session_id},
            )
            # Even if the request fails, verify the hash is untouched.
            assert resp.status_code >= 400, resp.text

            new_hash = _get_password_hash(email)

            # Hash must not have changed.
            assert new_hash == old_hash

            # The original password still verifies.
            assert bcrypt.checkpw(old_password.encode("utf-8"), new_hash.encode("utf-8"))

            # The new password does NOT verify against the stored hash.
            assert not bcrypt.checkpw(new_password.encode("utf-8"), new_hash.encode("utf-8"))
        finally:
            _delete_user(email)

    def test_wrong_current_password_error_message_mentions_current(self) -> None:
        """The error response should indicate the current password is
        incorrect (not a generic server error)."""
        email = "ac014_message@example.com"
        old_password = "old-password-123"
        new_password = "new-password-456"
        _create_user(email, old_password)
        try:
            session_id = _login(email, old_password)

            resp = client.post(
                "/auth/change-password",
                json={"current_password": "totally-wrong", "new_password": new_password},
                cookies={"session_id": session_id},
            )

            assert resp.status_code >= 400
            assert resp.status_code != 501, "Endpoint is not implemented (501 stub)"

            detail = resp.json().get("detail", "")
            lowered = detail.lower()
            assert "current" in lowered or "password" in lowered, (
                f"Error message should mention the current password; got: {detail!r}"
            )
        finally:
            _delete_user(email)
