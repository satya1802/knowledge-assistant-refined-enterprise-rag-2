"""Chat router: submit a question to the RAG flow.

``POST /chat`` validates the question and the conversation, then delegates
retrieval, grounded-answer generation, and citation construction to
``app.services.answer_chat_question`` (AC-065, AC-067, AC-068). The
``response_model`` and ``responses`` declare the agreed contract -- a
grounded or fallback answer with citations, or one of the error codes
below -- so the OpenAPI document the frontend is built against is complete.
A Gemini API error or quota failure during answer generation or embedding
creation is surfaced as ``CHAT_GEMINI_UNAVAILABLE`` rather than an
unhandled 500, and persisted documents, chunks, embeddings, and chat
history are left intact (AC-072).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import (
    CHAT_CONVERSATION_NOT_FOUND,
    CHAT_EMPTY_QUESTION,
    CHAT_GEMINI_UNAVAILABLE,
)
from app.models import Conversation, User
from app.routers.auth import get_current_user
from app.schemas import ChatRequest, ChatResponse, CitationItem
from app.services import GeminiUnavailableError, answer_chat_question

router = APIRouter(prefix="/chat", tags=["chat"])

# Module-level dependency singletons so ruff's B008 doesn't flag the defaults.
_db_dependency = Depends(get_db)
_current_user_dependency = Depends(get_current_user)


@router.post(
    "",
    response_model=ChatResponse,
    responses={
        CHAT_EMPTY_QUESTION.status_code: {"description": CHAT_EMPTY_QUESTION.detail},
        CHAT_CONVERSATION_NOT_FOUND.status_code: {
            "description": CHAT_CONVERSATION_NOT_FOUND.detail
        },
        CHAT_GEMINI_UNAVAILABLE.status_code: {"description": CHAT_GEMINI_UNAVAILABLE.detail},
    },
)
async def chat(
    request: ChatRequest,
    db: Session = _db_dependency,
    current_user: User = _current_user_dependency,
) -> ChatResponse:
    """Submit a question to the RAG flow (AC-065, AC-067, AC-068).

    The conversation must exist and belong to the signed-in user; the
    question must not be empty once surrounding whitespace is stripped.
    """
    question = request.question.strip()
    if not question:
        raise HTTPException(
            status_code=CHAT_EMPTY_QUESTION.status_code,
            detail=CHAT_EMPTY_QUESTION.detail,
        )

    conversation = db.execute(
        select(Conversation).where(
            Conversation.id == request.conversation_id,
            Conversation.user_id == current_user.id,
        )
    ).scalar_one_or_none()
    if conversation is None:
        raise HTTPException(
            status_code=CHAT_CONVERSATION_NOT_FOUND.status_code,
            detail=CHAT_CONVERSATION_NOT_FOUND.detail,
        )

    try:
        assistant_message = answer_chat_question(conversation, question, db)
    except GeminiUnavailableError:
        # AC-072: no partial message/citation was committed, so roll back the
        # flushed-but-uncommitted user message and surface a clear error --
        # all previously persisted documents, chunks, embeddings, chat
        # history, and users remain intact.
        db.rollback()
        raise HTTPException(
            status_code=CHAT_GEMINI_UNAVAILABLE.status_code,
            detail=CHAT_GEMINI_UNAVAILABLE.detail,
        ) from None

    return ChatResponse(
        answer=assistant_message.content,
        is_fallback=assistant_message.is_fallback,
        citations=[
            CitationItem(
                document_id=citation.document_id,
                filename=citation.filename,
                page_section=citation.page_section,
                chunk_id=citation.chunk_id,
            )
            for citation in assistant_message.citations
        ],
    )
