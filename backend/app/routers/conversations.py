"""Conversations router: create, list, view messages, and delete.

Every route is a stub that raises 501 until a development ticket implements
it. The ``response_model`` on each route declares the agreed contract so the
OpenAPI document the frontend is built against is complete from day one.
"""

from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.schemas import (
    ConversationCreateRequest,
    ConversationListItem,
    ConversationResponse,
    MessageListItem,
    MessageResponse,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("", response_model=ConversationResponse)
async def create_conversation(request: ConversationCreateRequest) -> None:
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("", response_model=list[ConversationListItem])
async def list_conversations() -> None:
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/{conversation_id}/messages", response_model=list[MessageListItem])
async def list_messages(conversation_id: UUID) -> None:
    raise HTTPException(status_code=501, detail="Not implemented")


@router.delete("/{conversation_id}", response_model=MessageResponse)
async def delete_conversation(conversation_id: UUID) -> None:
    raise HTTPException(status_code=501, detail="Not implemented")
