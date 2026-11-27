"""Conversations router: create, list, view messages, and delete.

``POST /conversations`` is implemented (AC-074): it creates a conversation
row tied to the signed-in user's ID and returns its details. The remaining
routes stay stubs -- raising 501 -- until a later ticket implements them; the
``response_model`` on each still declares the agreed contract so the OpenAPI
document the frontend is built against is complete.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.routers.auth import get_current_user
from app.schemas import (
    ConversationCreateRequest,
    ConversationListItem,
    ConversationResponse,
    MessageListItem,
    MessageResponse,
)
from app.services import create_conversation as create_conversation_for_user

router = APIRouter(prefix="/conversations", tags=["conversations"])

# Module-level dependency singletons so ruff's B008 doesn't flag the defaults.
_db_dependency = Depends(get_db)
_current_user_dependency = Depends(get_current_user)


@router.post("", response_model=ConversationResponse)
async def create_conversation(
    request: ConversationCreateRequest,
    db: Session = _db_dependency,
    current_user: User = _current_user_dependency,
) -> ConversationResponse:
    """Create a new chat conversation for the signed-in user (AC-074).

    The conversation is associated with ``current_user.id`` -- the user's
    identity always comes from the session, never from the request body.
    """
    conversation = create_conversation_for_user(current_user.id, request.title, db)
    return ConversationResponse(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
    )


@router.get("", response_model=list[ConversationListItem])
async def list_conversations() -> None:
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/{conversation_id}/messages", response_model=list[MessageListItem])
async def list_messages(conversation_id: UUID) -> None:
    raise HTTPException(status_code=501, detail="Not implemented")


@router.delete("/{conversation_id}", response_model=MessageResponse)
async def delete_conversation(conversation_id: UUID) -> None:
    raise HTTPException(status_code=501, detail="Not implemented")
