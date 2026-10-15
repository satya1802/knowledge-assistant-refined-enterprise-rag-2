"""Chat router: submit a question to the RAG flow.

Every route is a stub that raises 501 until a development ticket implements
it. The ``response_model`` on each route declares the agreed contract so the
OpenAPI document the frontend is built against is complete from day one.
"""

from fastapi import APIRouter, HTTPException

from app.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> None:
    raise HTTPException(status_code=501, detail="Not implemented")
