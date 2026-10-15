"""Documents router: upload, list, inspect, download, delete, and reindex.

``POST /documents`` and ``GET /documents`` are implemented in US-009-1.
``GET /documents/{id}`` and ``GET /documents/{id}/download`` are implemented
in US-017-1.  ``DELETE /documents/{id}`` is implemented in US-019-1.
Every other route remains a 501 stub until its development ticket lands.

Upload flow
-----------
1. Validate the session cookie (any authenticated user may call ``GET``;
   only ``Administrator`` users may call ``POST``).
2. Validate the file extension against the four supported types
   (PDF, DOCX, TXT, MD) -- 422 on mismatch.
3. Read the file content and enforce the 25 MB size limit -- 422 on overflow.
4. Persist the file to ``backend/uploads/`` using a UUID-based filename.
5. Insert a ``Document`` row with ``status='Processing'`` (processing itself
   is out of scope for this sprint).

``GET /documents`` always queries the ``Document`` table -- it never returns
a hardcoded or in-memory list, so documents survive restarts and page
refreshes (AC-042, AC-043, AC-044).
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Citation, Document, User
from app.routers.auth import get_current_user
from app.schemas import (
    DocumentDetail,
    DocumentListItem,
    DocumentResponse,
    DocumentStats,
    MessageResponse,
    ReindexResponse,
)

router = APIRouter(prefix="/documents", tags=["documents"])

# Module-level dependency singletons so ruff's B008 doesn't flag defaults.
_db_dependency = Depends(get_db)
_current_user_dependency = Depends(get_current_user)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Persistent upload directory: <repo>/backend/uploads
UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB in bytes

# Supported file types keyed by lowercase extension.  The value is the
# normalised type string stored in the ``Document.file_type`` column.
_SUPPORTED_EXTENSIONS: dict[str, str] = {
    ".pdf": "PDF",
    ".docx": "DOCX",
    ".txt": "TXT",
    ".md": "MD",
}

# MIME content types keyed by the normalised ``Document.file_type`` value.
# Used to set ``Content-Type`` on download responses.
_CONTENT_TYPES: dict[str, str] = {
    "PDF": "application/pdf",
    "DOCX": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "TXT": "text/plain",
    "MD": "text/markdown",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_admin(current_user: User) -> None:
    """Raise ``403`` unless *current_user* is an Administrator."""
    if current_user.role != "Administrator":
        raise HTTPException(status_code=403, detail="Administrator access required")


def _content_type_for(document: Document) -> str:
    """Return the MIME content type for a document based on its file type.

    Falls back to ``application/octet-stream`` for unknown types so the
    download is never sent without a content type.
    """
    return _CONTENT_TYPES.get(document.file_type, "application/octet-stream")


# ---------------------------------------------------------------------------
# Implemented routes
# ---------------------------------------------------------------------------


@router.post("", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile,
    db: Session = _db_dependency,
    current_user: User = _current_user_dependency,
) -> DocumentResponse:
    """Upload a document (admin only).

    Validates the file extension (PDF/DOCX/TXT/MD) and size (≤ 25 MB),
    persists the file to ``backend/uploads/``, and creates a ``Document``
    record with ``status='Processing'``.
    """
    _require_admin(current_user)

    # --- Type validation (by file extension) ---
    filename = file.filename or ""
    ext = Path(filename).suffix.lower()
    if ext not in _SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(_SUPPORTED_EXTENSIONS.values()))
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type. Supported types: {supported}",
        )

    # --- Size validation ---
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=422,
            detail="File exceeds the 25 MB size limit.",
        )

    # --- Persist file to durable directory ---
    doc_id = uuid.uuid4()
    saved_filename = f"{doc_id}{ext}"
    saved_path = UPLOAD_DIR / saved_filename
    saved_path.write_bytes(content)

    # --- Create Document DB record ---
    document = Document(
        id=doc_id,
        filename=filename,
        file_type=_SUPPORTED_EXTENSIONS[ext],
        file_size=len(content),
        file_path=str(saved_path),
        status="Processing",
        uploaded_by=current_user.id,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    return DocumentResponse(
        id=document.id,
        filename=document.filename,
        file_type=document.file_type,
        file_size=document.file_size,
        status=document.status,
        created_at=document.created_at,
    )


@router.get("", response_model=list[DocumentListItem])
async def list_documents(
    search: str | None = None,
    file_type: str | None = None,
    status: str | None = None,
    db: Session = _db_dependency,
    current_user: User = _current_user_dependency,
) -> list[DocumentListItem]:
    """Return all documents from the database (any authenticated user).

    Always queries the ``Document`` table -- never returns a hardcoded or
    in-memory list.  Optional ``search``, ``file_type``, and ``status``
    query parameters filter the result set.
    """
    query = select(Document).order_by(Document.created_at.desc())
    if search:
        query = query.where(Document.filename.ilike(f"%{search}%"))
    if file_type:
        query = query.where(Document.file_type == file_type)
    if status:
        query = query.where(Document.status == status)

    documents = db.execute(query).scalars().all()
    return [
        DocumentListItem(
            id=d.id,
            filename=d.filename,
            file_type=d.file_type,
            file_size=d.file_size,
            status=d.status,
            created_at=d.created_at,
            failure_reason=d.failure_reason,
        )
        for d in documents
    ]


@router.get("/{document_id}", response_model=DocumentDetail)
async def get_document(
    document_id: uuid.UUID,
    db: Session = _db_dependency,
    current_user: User = _current_user_dependency,
) -> DocumentDetail:
    """Return full metadata for a single document (any authenticated user).

    Includes filename, file type, file size, status, failure reason (if any),
    creation and last-updated timestamps (AC-048).  Returns 404 when the
    document does not exist (AC-049).
    """
    document = db.execute(select(Document).where(Document.id == document_id)).scalar_one_or_none()

    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    return DocumentDetail(
        id=document.id,
        filename=document.filename,
        file_type=document.file_type,
        file_size=document.file_size,
        status=document.status,
        failure_reason=document.failure_reason,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


@router.get("/{document_id}/download")
async def download_document(
    document_id: uuid.UUID,
    db: Session = _db_dependency,
    current_user: User = _current_user_dependency,
) -> FileResponse:
    """Stream the original uploaded file (any authenticated user).

    Returns the file as a ``FileResponse`` with the correct filename and
    content type in the ``Content-Disposition`` attachment header (AC-050).
    When the DB record exists but the file is missing from disk, returns a
    clear JSON error indicating the file is missing from storage (AC-051).
    """
    document = db.execute(select(Document).where(Document.id == document_id)).scalar_one_or_none()

    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = Path(document.file_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="The original file is missing from storage",
        )

    return FileResponse(
        path=str(file_path),
        media_type=_content_type_for(document),
        filename=document.filename,
    )


@router.delete("/{document_id}", response_model=MessageResponse)
async def delete_document(
    document_id: uuid.UUID,
    db: Session = _db_dependency,
    current_user: User = _current_user_dependency,
) -> MessageResponse:
    """Delete a document and all associated data (admin only).

    Removes the stored file from the filesystem (gracefully handling the case
    where it is already gone), deletes the ``Document`` record, and cascades
    cleanup to all chunks (via ORM ``cascade='all, delete-orphan'``) and
    related citations (explicitly queried and deleted, since SQLite does not
    enforce FK ``ON DELETE CASCADE`` at the database level by default).

    Returns ``404`` when the document does not exist and ``403`` when a
    non-admin user calls the endpoint (AC-052 through AC-055).
    """
    _require_admin(current_user)

    document = db.execute(select(Document).where(Document.id == document_id)).scalar_one_or_none()

    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    # --- Explicitly delete citations referencing this document ---
    # Citation has FKs to both documents and chunks with ondelete=CASCADE,
    # but SQLite does not enforce FK cascades by default, so we remove them
    # explicitly before deleting the document.
    citations = (
        db.execute(select(Citation).where(Citation.document_id == document_id)).scalars().all()
    )
    for citation in citations:
        db.delete(citation)

    # --- Capture file path before ORM deletion ---
    file_path = Path(document.file_path)

    # --- Delete document (ORM cascade='all, delete-orphan' removes chunks) ---
    db.delete(document)
    db.commit()

    # --- Remove file from filesystem (graceful if already gone) ---
    try:
        file_path.unlink()
    except FileNotFoundError:
        pass

    return MessageResponse(message="Document deleted successfully")


# ---------------------------------------------------------------------------
# Stubs -- 501 until their development tickets land
# ---------------------------------------------------------------------------


@router.get("/stats", response_model=DocumentStats)
async def document_stats() -> None:
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/{document_id}/reindex", response_model=ReindexResponse)
async def reindex_document(document_id: uuid.UUID) -> None:
    raise HTTPException(status_code=501, detail="Not implemented")
