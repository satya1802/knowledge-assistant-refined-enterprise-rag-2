"""Pydantic request and response models.

One pair per entity in the approved data model, plus the placeholder every
generated route returns until it has been implemented.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class StubResponse(BaseModel):
    """What a generated route returns until someone implements it.

    A stub that returns a typed body rather than raising keeps the service
    startable and its OpenAPI document complete, so the frontend can be built
    against the agreed shape while the handlers are still being implemented.
    """

    endpoint: str
    status: str = "not_implemented"
    detail: str = "Scaffolded from the approved API spec; no behaviour yet."


# --- Auth ---


class LoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    role: str


class MessageResponse(BaseModel):
    message: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


# --- Users ---


class CreateUserRequest(BaseModel):
    email: str
    password: str
    role: str


# --- Documents ---


class DocumentResponse(BaseModel):
    id: UUID
    filename: str
    file_type: str
    file_size: int
    status: str
    created_at: datetime


class DocumentListItem(BaseModel):
    id: UUID
    filename: str
    file_type: str
    file_size: int
    status: str
    created_at: datetime
    failure_reason: str | None = None


class DocumentDetail(BaseModel):
    id: UUID
    filename: str
    file_type: str
    file_size: int
    status: str
    failure_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class DocumentStats(BaseModel):
    total: int
    ready: int
    processing: int
    failed: int


class ReindexResponse(BaseModel):
    id: UUID
    status: str


# --- Conversations ---


class ConversationCreateRequest(BaseModel):
    title: str | None = None


class ConversationResponse(BaseModel):
    id: UUID
    title: str | None = None
    created_at: datetime


class ConversationListItem(BaseModel):
    id: UUID
    title: str | None = None
    created_at: datetime
    updated_at: datetime


class CitationItem(BaseModel):
    document_id: UUID
    filename: str
    page_section: str | None = None
    chunk_id: UUID


class MessageListItem(BaseModel):
    id: UUID
    role: str
    content: str
    is_fallback: bool
    citations: list[CitationItem] = []
    created_at: datetime


# --- Chat ---


class ChatRequest(BaseModel):
    conversation_id: UUID
    question: str


class ChatResponse(BaseModel):
    answer: str
    is_fallback: bool
    citations: list[CitationItem] = []


# --- Settings ---


class SettingsResponse(BaseModel):
    gemini_answer_model: str
    gemini_embedding_model: str
    cosine_threshold: float
    cookie_secure_flag: bool


class SettingsUpdateRequest(BaseModel):
    gemini_answer_model: str | None = None
    gemini_embedding_model: str | None = None
    cosine_threshold: float | None = None
    cookie_secure_flag: bool | None = None