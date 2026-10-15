"""Integration tests for POST /auth/login (US-002-1).

Covers:
  AC-004 — valid credentials set an HTTP-only cookie and return {id, email, role}.
  AC-005 — wrong email and wrong password return the same generic error.
  AC-006 — cookie is HTTP-only; Secure flag is configurable via COOKIE_SECURE.
  AC-011 — 5 failures within 15 min lock the email; a 6th attempt is rejected
           with a lockout message regardless of password correctness.
  AC-012 — after 15 minutes since lockout began, the lockout expires and
           attempts are accepted again.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import bcrypt
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import SessionLocal
from app.main import app
from app.models import LoginAttempt, User

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
    """Remove a user and its login attempts from the test database."""
    with SessionLocal() as db:
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is not None:
            db.delete(user)
        attempts = db.execute(
            select(LoginAttempt).where(LoginAttempt.email == email)
        ).scalars().all()
        for a in attempts:
            db.delete(a)
        db.commit()


def _set_locked_until(email: str, locked_until: datetime | None) -> None:
    """Directly set the locked_until timestamp on a user record."""
    with SessionLocal() as db:
        user = db.execute(select(User).where(User.email == email)).scalar_one()
        user.locked_until = locked_until
        if locked_until is None:
            user.failed_login_count = 0
        db.commit()


def _age_out_attempts(email: str, minutes_ago: int = 20) -> None:
    """Set all LoginAttempt timestamps for *email* far into the past so they
    fall outside the 15-minute lockout window."""
    old = datetime.now(UTC) - timedelta(minutes=minutes_ago)
    with SessionLocal() as db:
        attempts = (
            db.execute(select(LoginAttempt).where(LoginAttempt.email == email))
            .scalars()
            .all()
        )
        for a in attempts:
            a.attempted_at = old
        db.commit()


# ---------------------------------------------------------------------------
# AC-004 — valid credentials → cookie + profile
# ---------------------------------------------------------------------------


class TestSuccessfulLogin:
    def test_valid_credentials_returns_user_profile(self) -> None:
        email = "ac004_success@example.com"
        password = "correct-password"
        _create_user(email, password)
        try:
            resp = client.post("/auth/login", json={"email": email, "password": password})

            assert resp.status_code == 200
            body = resp.json()
            assert set(body.keys()) == {"id", "email", "role"}
            assert body["email"] == email
            assert body["role"] == "User"
            assert isinstance(body["id"], int)
        finally:
            _delete_user(email)

    def test_valid_credentials_sets_session_cookie(self) -> None:
        email = "ac004_cookie@example.com"
        password = "correct-password"
        _create_user(email, password)
        try:
            resp = client.post("/auth/login", json={"email": email, "password": password})

            assert resp.status_code == 200
            # The Set-Cookie header must be present.
            set_cookie = resp.headers.get("set-cookie", "")
            assert "session_id=" in set_cookie
        finally:
            _delete_user(email)

    def test_successful_login_creates_session_record(self) -> None:
        email = "ac004_session@example.com"
        password = "correct-password"
        user = _create_user(email, password)
        try:
            resp = client.post("/auth/login", json={"email": email, "password": password})

            assert resp.status_code == 200
            from app.models import Session as SessionModel

            with SessionLocal() as db:
                sessions = (
                    db.execute(
                        select(SessionModel).where(SessionModel.user_id == user.id)
                    )
                    .scalars()
                    .all()
                )
                assert len(sessions) == 1
                assert sessions[0].expires_at is not None
        finally:
            _delete_user(email)

    def test_successful_login_clears_failed_attempts(self) -> None:
        email = "ac004_clear@example.com"
        password = "correct-password"
        _create_user(email, password)
        try:
            # Two failed attempts first.
            client.post("/auth/login", json={"email": email, "password": "wrong"})
            client.post("/auth/login", json={"email": email, "password": "wrong"})

            with SessionLocal() as db:
                user = db.execute(select(User).where(User.email == email)).scalar_one()
                assert user.failed_login_count == 2

            # Now succeed.
            resp = client.post("/auth/login", json={"email": email, "password": password})
            assert resp.status_code == 200

            with SessionLocal() as db:
                user = db.execute(select(User).where(User.email == email)).scalar_one()
                assert user.failed_login_count == 0
                assert user.locked_until is None
        finally:
            _delete_user(email)


# ---------------------------------------------------------------------------
# AC-005 — wrong email and wrong password return the same generic error
# ---------------------------------------------------------------------------


class TestGenericCredentialError:
    def test_wrong_password_returns_generic_error(self) -> None:
        email = "ac005_wrongpw@example.com"
        _create_user(email, "correct-password")
        try:
            resp = client.post(
                "/auth/login", json={"email": email, "password": "wrong-password"}
            )

            assert resp.status_code == 401
            assert resp.json()["detail"] == "Invalid email or password"
        finally:
            _delete_user(email)

    def test_wrong_email_returns_generic_error(self) -> None:
        resp = client.post(
            "/auth/login",
            json={"email": "nonexistent@example.com", "password": "any-password"},
        )

        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid email or password"

    def test_wrong_email_and_wrong_password_have_same_message(self) -> None:
        email = "ac005_compare@example.com"
        _create_user(email, "correct-password")
        try:
            wrong_pw = client.post(
                "/auth/login", json={"email": email, "password": "bad"}
            )
            wrong_email = client.post(
                "/auth/login",
                json={"email": "nonexistent@example.com", "password": "bad"},
            )

            assert wrong_pw.status_code == wrong_email.status_code
            assert wrong_pw.json()["detail"] == wrong_email.json()["detail"]
        finally:
            _delete_user(email)


# ---------------------------------------------------------------------------
# AC-006 — cookie is HTTP-only; Secure flag is configurable
# ---------------------------------------------------------------------------


class TestCookieAttributes:
    def test_cookie_is_http_only(self) -> None:
        email = "ac006_httponly@example.com"
        password = "correct-password"
        _create_user(email, password)
        try:
            resp = client.post("/auth/login", json={"email": email, "password": password})

            assert resp.status_code == 200
            set_cookie = resp.headers.get("set-cookie", "")
            assert "httponly" in set_cookie.lower()
        finally:
            _delete_user(email)

    def test_cookie_secure_disabled_by_default(self) -> None:
        email = "ac006_secure_off@example.com"
        password = "correct-password"
        _create_user(email, password)
        os.environ.pop("COOKIE_SECURE", None)
        try:
            resp = client.post("/auth/login", json={"email": email, "password": password})

            assert resp.status_code == 200
            set_cookie = resp.headers.get("set-cookie", "")
            # Secure should NOT be present when COOKIE_SECURE is not set / false.
            assert "secure" not in set_cookie.lower()
        finally:
            _delete_user(email)

    def test_cookie_secure_enabled_via_env(self) -> None:
        email = "ac006_secure_on@example.com"
        password = "correct-password"
        _create_user(email, password)
        os.environ["COOKIE_SECURE"] = "true"
        try:
            resp = client.post("/auth/login", json={"email": email, "password": password})

            assert resp.status_code == 200
            set_cookie = resp.headers.get("set-cookie", "")
            assert "secure" in set_cookie.lower()
        finally:
            os.environ.pop("COOKIE_SECURE", None)
            _delete_user(email)

    def test_cookie_secure_disabled_via_env_false(self) -> None:
        email = "ac006_secure_false@example.com"
        password = "correct-password"
        _create_user(email, password)
        os.environ["COOKIE_SECURE"] = "false"
        try:
            resp = client.post("/auth/login", json={"email": email, "password": password})

            assert resp.status_code == 200
            set_cookie = resp.headers.get("set-cookie", "")
            assert "secure" not in set_cookie.lower()
        finally:
            os.environ.pop("COOKIE_SECURE", None)
            _delete_user(email)


# ---------------------------------------------------------------------------
# AC-011 — 5 failures within 15 min → 6th attempt rejected with lockout
# ---------------------------------------------------------------------------


class TestLockoutTrigger:
    def test_sixth_attempt_rejected_with_lockout_message(self) -> None:
        email = "ac011_lockout@example.com"
        password = "correct-password"
        _create_user(email, password)
        try:
            # 5 failed attempts.
            for _ in range(5):
                resp = client.post(
                    "/auth/login", json={"email": email, "password": "wrong"}
                )
                assert resp.status_code == 401
                assert resp.json()["detail"] == "Invalid email or password"

            # 6th attempt — should be locked, even with the correct password.
            resp = client.post(
                "/auth/login", json={"email": email, "password": password}
            )

            assert resp.status_code == 423
            detail = resp.json()["detail"]
            assert detail != "Invalid email or password"
            assert "lock" in detail.lower()
        finally:
            _delete_user(email)

    def test_sixth_attempt_rejected_even_with_wrong_password(self) -> None:
        email = "ac011_lockout_wrong@example.com"
        password = "correct-password"
        _create_user(email, password)
        try:
            for _ in range(5):
                client.post("/auth/login", json={"email": email, "password": "wrong"})

            # 6th attempt with wrong password — locked, not generic error.
            resp = client.post(
                "/auth/login", json={"email": email, "password": "also-wrong"}
            )

            assert resp.status_code == 423
            assert resp.json()["detail"] != "Invalid email or password"
        finally:
            _delete_user(email)

    def test_lockout_sets_locked_until(self) -> None:
        email = "ac011_locked_until@example.com"
        password = "correct-password"
        _create_user(email, password)
        try:
            for _ in range(5):
                client.post("/auth/login", json={"email": email, "password": "wrong"})

            with SessionLocal() as db:
                user = db.execute(select(User).where(User.email == email)).scalar_one()
                assert user.locked_until is not None
                assert user.locked_until > datetime.now(UTC)
        finally:
            _delete_user(email)

    def test_four_failures_do_not_lock(self) -> None:
        email = "ac011_four@example.com"
        password = "correct-password"
        _create_user(email, password)
        try:
            for _ in range(4):
                resp = client.post(
                    "/auth/login", json={"email": email, "password": "wrong"}
                )
                assert resp.status_code == 401

            # 5th attempt with correct password should succeed.
            resp = client.post(
                "/auth/login", json={"email": email, "password": password}
            )
            assert resp.status_code == 200
        finally:
            _delete_user(email)

    def test_lockout_for_nonexistent_email(self) -> None:
        """Lockout should also apply to emails that have no user record."""
        email = "ac011_nouser@example.com"
        try:
            for _ in range(5):
                resp = client.post(
                    "/auth/login", json={"email": email, "password": "wrong"}
                )
                assert resp.status_code == 401

            # 6th attempt — should be locked.
            resp = client.post(
                "/auth/login", json={"email": email, "password": "wrong"}
            )
            assert resp.status_code == 423
            assert resp.json()["detail"] != "Invalid email or password"
        finally:
            # Clean up login attempts for this email.
            with SessionLocal() as db:
                attempts = (
                    db.execute(
                        select(LoginAttempt).where(LoginAttempt.email == email)
                    )
                    .scalars()
                    .all()
                )
                for a in attempts:
                    db.delete(a)
                db.commit()


# ---------------------------------------------------------------------------
# AC-012 — lockout expires after 15 minutes
# ---------------------------------------------------------------------------


class TestLockoutExpiry:
    def test_lockout_expires_after_15_minutes(self) -> None:
        email = "ac012_expire@example.com"
        password = "correct-password"
        _create_user(email, password)
        try:
            # Trigger lockout with 5 failures.
            for _ in range(5):
                client.post("/auth/login", json={"email": email, "password": "wrong"})

            # Simulate 15+ minutes having passed: age out the attempt
            # timestamps and set locked_until to the past.
            _age_out_attempts(email)
            past = datetime.now(UTC) - timedelta(minutes=1)
            _set_locked_until(email, past)

            # Now login with correct password should succeed.
            resp = client.post(
                "/auth/login", json={"email": email, "password": password}
            )
            assert resp.status_code == 200
            assert resp.json()["email"] == email
        finally:
            _delete_user(email)

    def test_lockout_expiry_resets_failed_count(self) -> None:
        email = "ac012_reset@example.com"
        password = "correct-password"
        _create_user(email, password)
        try:
            for _ in range(5):
                client.post("/auth/login", json={"email": email, "password": "wrong"})

            with SessionLocal() as db:
                user = db.execute(select(User).where(User.email == email)).scalar_one()
                assert user.failed_login_count >= 5
                assert user.locked_until is not None

            # Simulate 15+ minutes having passed.
            _age_out_attempts(email)
            past = datetime.now(UTC) - timedelta(minutes=1)
            _set_locked_until(email, past)

            # A failed attempt after expiry should NOT immediately re-lock
            # because the old attempts are now outside the 15-minute window.
            resp = client.post(
                "/auth/login", json={"email": email, "password": "wrong-again"}
            )
            assert resp.status_code == 401
            assert resp.json()["detail"] == "Invalid email or password"

            with SessionLocal() as db:
                user = db.execute(select(User).where(User.email == email)).scalar_one()
                assert user.locked_until is None
        finally:
            _delete_user(email)

    def test_can_login_with_correct_password_after_expiry(self) -> None:
        email = "ac012_login_after@example.com"
        password = "correct-password"
        _create_user(email, password)
        try:
            for _ in range(5):
                client.post("/auth/login", json={"email": email, "password": "wrong"})

            # Verify locked.
            resp = client.post(
                "/auth/login", json={"email": email, "password": password}
            )
            assert resp.status_code == 423

            # Expire the lockout (age out attempts + set locked_until to past).
            _age_out_attempts(email)
            past = datetime.now(UTC) - timedelta(minutes=1)
            _set_locked_until(email, past)

            # Should now succeed.
            resp = client.post(
                "/auth/login", json={"email": email, "password": password}
            )
            assert resp.status_code == 200
        finally:
            _delete_user(email)