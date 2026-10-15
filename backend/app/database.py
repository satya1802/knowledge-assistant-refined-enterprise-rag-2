"""Engine, session factory and the request-scoped session dependency.

SQLite by default so a fresh clone runs with nothing but `pip install -r
requirements.txt` -- the approved architecture may name Postgres or MySQL, but
naming one is not the same as having one, and a scaffold that cannot start
without a database server is a scaffold nobody runs. Point `DATABASE_URL` at
the real thing when it exists; nothing else has to change.

``TZDateTime`` is a custom type that stores timezone-aware datetimes as
timezone-naive UTC values and restores the UTC timezone on read.  SQLite has
no native timezone support, so without this every datetime round-trips as a
naive value and the application silently drifts.  Using a ``TypeDecorator``
rather than a PRAGMA keeps the behaviour identical on PostgreSQL.
"""

import os
from collections.abc import Iterator
from datetime import UTC, datetime

from sqlalchemy import DateTime, TypeDecorator, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")

# SQLite rejects a connection made on one thread and used on another, which is
# exactly what happens when FastAPI runs a sync dependency in its threadpool.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Declarative base that every generated model inherits."""


class TZDateTime(TypeDecorator):
    """Store datetimes as UTC-naive and restore UTC on read.

    SQLite persists timezone-less ``datetime`` values.  Without normalisation
    a timezone-aware ``datetime`` written from Python loses its ``tzinfo`` on
    the way back, so the application would treat a UTC timestamp as local.
    This type converts every value to UTC before storage and stamps it with
    ``UTC`` on retrieval, so the rest of the code can rely on every
    ``datetime`` being timezone-aware and in UTC regardless of backend.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: object) -> datetime | None:
        if value is not None:
            if value.tzinfo is None:
                # Treat naive datetimes as UTC rather than raising -- the
                # application convention is that every naive datetime is UTC.
                value = value.replace(tzinfo=UTC)
            value = value.astimezone(UTC).replace(tzinfo=None)
        return value

    def process_result_value(self, value: datetime | None, dialect: object) -> datetime | None:
        if value is not None:
            value = value.replace(tzinfo=UTC)
        return value


def get_db() -> Iterator[Session]:
    """One session per request, closed even when the handler raises."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
