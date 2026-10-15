"""SQLAlchemy models for the nine entities the approved data model declares.

``Base`` is already bound to the engine in ``app.database``, and ``main.py``
imports this module before it calls ``Base.metadata.create_all``, so the tables
are created on startup. The ``embedding`` column on ``chunks`` uses the pgvector
SQLAlchemy ``Vector`` type, which stores as text on SQLite (for local
development) and as a native ``vector(768)`` on PostgreSQL with the pgvector
extension (for production).

ID strategy
-----------
``User`` and other integer-keyed tables use ``BigInteger`` with
``with_variant(Integer, "sqlite")`` and the default ``autoincrement=True``
behavior for single-column integer primary keys, so the primary key is
**database-generated** on both SQLite and PostgreSQL. On SQLite
``BigInteger`` is compiled as ``INTEGER`` (via ``with_variant``) so the
engine's native autoincrement (rowid) applies; on PostgreSQL ``BigInteger``
with autoincrement emits ``BIGSERIAL``, a sequence-backed column.
Python-side ``default=`` is never used for these IDs.

``Session`` is the exception: its primary key is a UUID (standard 4) generated
in Python, stored as a string in the session cookie, and converted back to a
``uuid.UUID`` before any database lookup (see :func:`parse_session_id`).

All ``datetime`` columns use :class:`app.database.TZDateTime` so SQLite's
timezone-less values are consistently treated as UTC.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TZDateTime

__all__ = [
    "Base",
    "User",
    "Session",
    "LoginAttempt",
    "Document",
    "Chunk",
    "Conversation",
    "Message",
    "Citation",
    "Settings",
    "parse_session_id",
]


def _utcnow() -> datetime:
    return datetime.now(UTC)


def parse_session_id(raw: str | uuid.UUID) -> uuid.UUID:
    """Convert a cookie session ID (string) to ``uuid.UUID`` for DB lookups.

    Session IDs are stored as a string in the cookie and as a native UUID in
    the database. Passing the raw string directly to a query would cause a
    type mismatch on some backends; this helper normalises the input to
    ``uuid.UUID`` before the query is issued.

    Raises ``ValueError`` if the string is not a valid UUID.
    """
    if isinstance(raw, uuid.UUID):
        return raw
    return uuid.UUID(str(raw))


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="User")
    failed_login_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        TZDateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    sessions: Mapped[list[Session]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    documents: Mapped[list[Document]] = relationship(back_populates="uploader")
    conversations: Mapped[list[Conversation]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=_utcnow)

    user: Mapped[User] = relationship(back_populates="sessions")

    @staticmethod
    def lookup_id(raw: str | uuid.UUID) -> uuid.UUID:
        """Convert a cookie session-ID string to ``uuid.UUID`` for queries."""
        return parse_session_id(raw)


class LoginAttempt(Base):
    __tablename__ = "login_attempts"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    attempted_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=_utcnow)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(10), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_by: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("users.id"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        TZDateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    uploader: Mapped[User] = relationship(back_populates="documents")
    chunks: Mapped[list[Chunk]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_section: Mapped[str | None] = mapped_column(String(255), nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(768), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=_utcnow)

    document: Mapped[Document] = relationship(back_populates="chunks")
    citations: Mapped[list[Citation]] = relationship(back_populates="chunk")


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        TZDateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    user: Mapped[User] = relationship(back_populates="conversations")
    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=_utcnow)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
    citations: Mapped[list[Citation]] = relationship(
        back_populates="message", cascade="all, delete-orphan"
    )


class Citation(Base):
    __tablename__ = "citations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    page_section: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=_utcnow)

    message: Mapped[Message] = relationship(back_populates="citations")
    document: Mapped[Document] = relationship()
    chunk: Mapped[Chunk] = relationship(back_populates="citations")


class Settings(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    gemini_answer_model: Mapped[str] = mapped_column(
        String(100), nullable=False, default="gemini-2.0-flash"
    )
    gemini_embedding_model: Mapped[str] = mapped_column(
        String(100), nullable=False, default="text-embedding-004"
    )
    cosine_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.75)
    cookie_secure_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        TZDateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )