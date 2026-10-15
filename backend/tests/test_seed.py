"""Tests for User/Session models, admin seeding, BigInteger IDs, UUID lookup,
and SQLite timezone-as-UTC handling (US-001-1).

Each test uses an in-memory SQLite database to keep them hermetic and fast.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base, TZDateTime
from app.models import Session as SessionModel
from app.models import User, parse_session_id
from app.seed import ADMIN_EMAIL, ADMIN_PASSWORD, ADMIN_ROLE, seed_admin, verify_password


@pytest.fixture()
def db_session() -> Session:
    """Fresh in-memory SQLite database for each test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


# ---------------------------------------------------------------------------
# AC-001: First startup on empty user table creates the admin.
# ---------------------------------------------------------------------------


def test_seed_creates_admin_on_empty_table(db_session: Session) -> None:
    seed_admin(db_session)

    user = db_session.execute(select(User).where(User.email == ADMIN_EMAIL)).scalar_one()

    assert user.email == ADMIN_EMAIL
    assert user.role == ADMIN_ROLE
    # Password is a bcrypt hash, not the plaintext.
    assert user.password_hash != ADMIN_PASSWORD
    assert verify_password(ADMIN_PASSWORD, user.password_hash)


def test_seed_password_is_bcrypt_hash(db_session: Session) -> None:
    seed_admin(db_session)

    user = db_session.execute(select(User).where(User.email == ADMIN_EMAIL)).scalar_one()

    # bcrypt hashes always start with $2
    assert user.password_hash.startswith("$2")
    assert len(user.password_hash) >= 50


def test_seed_password_verifies_with_bcrypt_directly(db_session: Session) -> None:
    """Independently verify the hash with bcrypt.checkpw, not through seed's
    own verify_password wrapper, to avoid a circular self-test."""
    seed_admin(db_session)

    user = db_session.execute(select(User).where(User.email == ADMIN_EMAIL)).scalar_one()

    assert bcrypt.checkpw(ADMIN_PASSWORD.encode("utf-8"), user.password_hash.encode("utf-8"))
    # A wrong password must NOT verify.
    assert not bcrypt.checkpw(b"wrong-password", user.password_hash.encode("utf-8"))


# ---------------------------------------------------------------------------
# AC-002: Re-running seeding leaves an existing admin unchanged.
# ---------------------------------------------------------------------------


def test_seed_idempotent_no_duplicate(db_session: Session) -> None:
    seed_admin(db_session)
    seed_admin(db_session)  # restart

    users = db_session.execute(select(User).where(User.email == ADMIN_EMAIL)).scalars().all()
    assert len(users) == 1


def test_seed_does_not_reset_password(db_session: Session) -> None:
    seed_admin(db_session)

    user = db_session.execute(select(User).where(User.email == ADMIN_EMAIL)).scalar_one()

    # Simulate an admin password change.
    new_hash = bcrypt.hashpw(b"changed-password", bcrypt.gensalt()).decode("utf-8")
    user.password_hash = new_hash
    db_session.commit()

    # Restart -- seeding should leave the changed password alone.
    seed_admin(db_session)

    user = db_session.execute(select(User).where(User.email == ADMIN_EMAIL)).scalar_one()
    assert user.password_hash == new_hash
    assert not verify_password(ADMIN_PASSWORD, user.password_hash)
    assert verify_password("changed-password", user.password_hash)


def test_seed_preserves_original_hash_on_rerun(db_session: Session) -> None:
    """A second seed_admin call must leave the exact bcrypt hash untouched."""
    seed_admin(db_session)

    user = db_session.execute(select(User).where(User.email == ADMIN_EMAIL)).scalar_one()
    original_hash = user.password_hash

    seed_admin(db_session)  # restart

    user = db_session.execute(select(User).where(User.email == ADMIN_EMAIL)).scalar_one()
    assert user.password_hash == original_hash


# ---------------------------------------------------------------------------
# AC-003: Plaintext password is never stored or logged.
# ---------------------------------------------------------------------------


def test_plaintext_password_not_in_database(db_session: Session) -> None:
    seed_admin(db_session)

    user = db_session.execute(select(User).where(User.email == ADMIN_EMAIL)).scalar_one()
    assert ADMIN_PASSWORD not in user.password_hash
    assert user.password_hash != ADMIN_PASSWORD


def test_plaintext_password_not_in_any_database_column(db_session: Session) -> None:
    """Scan every text column of every table for the plaintext password."""
    seed_admin(db_session)

    raw_conn = db_session.connection().connection
    cursor = raw_conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    table_names = [row[0] for row in cursor.fetchall()]

    for table_name in table_names:
        cursor.execute(f"SELECT * FROM {table_name}")  # noqa: S608
        col_names = [desc[0] for desc in cursor.description]
        for row in cursor.fetchall():
            for col_name, value in zip(col_names, row, strict=False):
                if isinstance(value, str) and ADMIN_PASSWORD in value:
                    pytest.fail(f"Plaintext password found in {table_name}.{col_name}: {value!r}")
    cursor.close()


def test_plaintext_password_not_logged(
    db_session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    seed_admin(db_session)

    for record in caplog.records:
        assert ADMIN_PASSWORD not in record.getMessage()


# ---------------------------------------------------------------------------
# AC-115: Database-generated BigInteger IDs (SQLite + PostgreSQL compatible).
# ---------------------------------------------------------------------------


def test_user_id_is_database_generated(db_session: Session) -> None:
    """The user gets an auto-generated integer ID from the database, not Python."""
    user = User(
        email="test@example.com",
        password_hash="$2b$12$dummyhash",
        role="User",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert isinstance(user.id, int)
    assert user.id >= 1


def test_user_id_autoincrements(db_session: Session) -> None:
    u1 = User(email="a@example.com", password_hash="h", role="User")
    u2 = User(email="b@example.com", password_hash="h", role="User")
    db_session.add_all([u1, u2])
    db_session.commit()
    db_session.refresh(u1)
    db_session.refresh(u2)

    assert u2.id == u1.id + 1


def test_user_id_is_biginteger_type() -> None:
    """The column type is BigInteger (with Integer variant for SQLite)."""
    col = User.__table__.c.id
    # The base type is BigInteger.
    assert "BigInteger" in type(col.type).__name__ or hasattr(col.type, "impl")


def test_multiple_users_increment_sequentially(db_session: Session) -> None:
    """Three users get IDs 1, 2, 3 -- no gaps, no corruption."""
    ids = []
    for i in range(3):
        u = User(email=f"user{i}@example.com", password_hash="h", role="User")
        db_session.add(u)
        db_session.commit()
        db_session.refresh(u)
        ids.append(u.id)

    assert ids == [1, 2, 3]


# ---------------------------------------------------------------------------
# AC-116: UUID session IDs with conversion helper.
# ---------------------------------------------------------------------------


def test_session_id_is_uuid(db_session: Session) -> None:
    user = User(email="s@example.com", password_hash="h", role="User")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    session = SessionModel(
        user_id=user.id,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    assert isinstance(session.id, uuid.UUID)
    assert session.id.version == 4


def test_parse_session_id_converts_string_to_uuid() -> None:
    test_uuid = uuid.uuid4()
    parsed = parse_session_id(str(test_uuid))
    assert isinstance(parsed, uuid.UUID)
    assert parsed == test_uuid


def test_parse_session_id_passes_through_uuid() -> None:
    test_uuid = uuid.uuid4()
    parsed = parse_session_id(test_uuid)
    assert parsed == test_uuid


def test_parse_session_id_raises_on_invalid() -> None:
    with pytest.raises(ValueError):
        parse_session_id("not-a-uuid")


def test_session_lookup_via_converted_string_id(db_session: Session) -> None:
    """Looking up a session by cookie string must convert to UUID first."""
    user = User(email="lookup@example.com", password_hash="h", role="User")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    session = SessionModel(
        user_id=user.id,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    cookie_value = str(session.id)  # string as stored in the cookie
    parsed = parse_session_id(cookie_value)
    found = db_session.execute(select(SessionModel).where(SessionModel.id == parsed)).scalar_one()

    assert found.id == session.id


def test_raw_string_session_lookup_raises_type_error(db_session: Session) -> None:
    """Passing the raw cookie string without conversion must fail -- this is
    the type mismatch the conversion helper exists to prevent."""
    user = User(email="rawstr@example.com", password_hash="h", role="User")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    session = SessionModel(
        user_id=user.id,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    cookie_value = str(session.id)
    with pytest.raises(Exception):  # noqa: B017 -- broad on purpose
        db_session.execute(select(SessionModel).where(SessionModel.id == cookie_value)).scalar_one()


def test_session_lookup_id_static_method() -> None:
    test_uuid = uuid.uuid4()
    parsed = SessionModel.lookup_id(str(test_uuid))
    assert parsed == test_uuid


# ---------------------------------------------------------------------------
# AC-117: SQLite timezone-less datetimes treated as UTC.
# ---------------------------------------------------------------------------


def test_tzdatetime_stores_and_retrieves_utc(db_session: Session) -> None:
    """A timezone-aware UTC datetime round-trips with UTC preserved."""
    user = User(email="tz@example.com", password_hash="h", role="User")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.created_at.tzinfo is not None
    assert user.created_at.utcoffset() == timedelta(0)


def test_tzdatetime_converts_aware_non_utc_to_utc(db_session: Session) -> None:
    """A timezone-aware non-UTC datetime is stored as UTC."""
    from datetime import timezone

    # +05:30 timezone
    ist = timezone(timedelta(hours=5, minutes=30))
    original = datetime(2026, 1, 15, 10, 30, 0, tzinfo=ist)  # 05:00 UTC

    user = User(
        email="ist@example.com",
        password_hash="h",
        role="User",
        created_at=original,
        updated_at=original,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Retrieved value should be UTC equivalent.
    assert user.created_at.tzinfo is not None
    assert user.created_at.utcoffset() == timedelta(0)
    assert user.created_at.hour == 5
    assert user.created_at.minute == 0


def test_tzdatetime_round_trips_specific_utc_value(db_session: Session) -> None:
    """A known UTC datetime survives a write-read cycle unchanged."""
    specific = datetime(2026, 6, 15, 12, 30, 45, tzinfo=UTC)
    user = User(
        email="roundtrip@example.com",
        password_hash="h",
        role="User",
        created_at=specific,
        updated_at=specific,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.created_at == specific
    assert user.created_at.tzinfo is not None
    assert user.created_at.utcoffset() == timedelta(0)


def test_tzdatetime_treats_naive_as_utc() -> None:
    """TZDateTime treats a naive datetime as UTC on bind."""
    tz = TZDateTime()
    naive = datetime(2026, 6, 15, 12, 0, 0)
    result = tz.process_bind_param(naive, None)
    # Stored as naive (no tzinfo) but the value is the same UTC instant.
    assert result is not None
    assert result.tzinfo is None
    assert result.hour == 12


def test_tzdatetime_result_value_has_utc_tzinfo() -> None:
    """Retrieved naive datetime gets UTC tzinfo attached."""
    tz = TZDateTime()
    naive = datetime(2026, 6, 15, 12, 0, 0)
    result = tz.process_result_value(naive, None)
    assert result is not None
    assert result.tzinfo is not None
    assert result.utcoffset() == timedelta(0)
