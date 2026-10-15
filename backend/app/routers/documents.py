"""Documents router: upload, list, inspect, download, delete, and reindex.

Every route is a stub that raises 501 until a development ticket implements
it. The ``response_model`` on each route declares the agreed contract so the
OpenAPI document the frontend is built against is complete from day one.
"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, UploadFile

from app.schemas import (
    DocumentDetail,
    DocumentListItem,
    DocumentResponse,
    DocumentStats,
    MessageResponse,
    ReindexResponse,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=DocumentResponse)
async def upload_document(file: UploadFile) -> None:
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("", response_model=list[DocumentListItem])
async def list_documents(
    search: str | None = None,
    file_type: str | None = None,
    status: str | None = None,
) -> None:
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/stats", response_model=DocumentStats)
async def document_stats() -> None:
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/{document_id}", response_model=DocumentDetail)
async def get_document(document_id: UUID) -> None:
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/{document_id}/download")
async def download_document(document_id: UUID) -> None:
    raise HTTPException(status_code=501, detail="Not implemented")


@router.delete("/{document_id}", response_model=MessageResponse)
async def delete_document(document_id: UUID) -> None:
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/{document_id}/reindex", response_model=ReindexResponse)
async def reindex_document(document_id: UUID) -> None:
    raise HTTPException(status_code=501, detail="Not implemented")
