"""Document processing pipeline: extraction, chunking, and embedding.

This module hosts the background-job entry point (:func:`process_document`)
and the embedding-generation step (:func:`generate_embeddings`) that US-013
implements.

Pipeline overview
-----------------
1. **Extraction** — read text (and page metadata) from the uploaded file.
2. **Chunking** — split the extracted text into semantically bounded chunks
   and persist them as ``Chunk`` rows.
3. **Embedding** — for every chunk, call the Google Gemini embedding API
   using the model name stored in ``Settings.gemini_embedding_model`` and
   persist the resulting 768-dimensional vector on the chunk row.

Steps 1 and 2 are owned by sibling tickets (``extraction.py``,
``chunking.py``); when they land, :func:`process_document` will call them
before :func:`generate_embeddings`.  Until then the pipeline function calls
the embedding step directly so that the embedding logic is exercised and
independently testable.

Embedding step (US-013)
-----------------------
:func:`generate_embeddings` is deliberately decoupled from the rq job so it
can be unit-tested in isolation.  It reads the live model name from
``get_current_settings(db).gemini_embedding_model`` at call time (never
cached), configures the ``google.generativeai`` SDK with the
``GEMINI_API_KEY`` environment variable, and calls ``genai.embed_content``
once per chunk that does not yet have an embedding.

Error handling
~~~~~~~~~~~~~~
On *any* Gemini API error (invalid/missing key, quota exhaustion, network
failure, unexpected dimension) the document status is set to ``"Failed"``
with a human-readable ``failure_reason``.  All chunks and any embeddings
already persisted are retained — nothing is deleted.  On success (every
chunk has a 768-dimensional embedding) the document status is set to
``"Ready"``.
"""

from __future__ import annotations

import logging
import os
import uuid

import google.generativeai as genai
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Chunk, Document
from app.services import get_current_settings

logger = logging.getLogger(__name__)

# The ``chunks`` table stores a ``Vector(768)`` column, so every embedding
# must be exactly 768-dimensional.
_EMBEDDING_DIMENSION = 768


def _normalise_model_name(model_name: str) -> str:
    """Return *model_name* prefixed with ``models/`` if it is not already.

    The ``google.generativeai`` SDK requires model names to be fully
    qualified (``models/text-embedding-004``).  ``Settings.gemini_embedding_model``
    stores the bare name (``text-embedding-004``), so this helper adds the
    prefix when it is missing.
    """
    if model_name.startswith("models/"):
        return model_name
    return f"models/{model_name}"


def generate_embeddings(document_id: uuid.UUID, db: Session) -> None:
    """Generate and persist Gemini embeddings for every chunk of a document.

    Reads the embedding model name from
    ``get_current_settings(db).gemini_embedding_model`` at runtime and calls
    the Google Gemini embedding API (``genai.embed_content``) once per chunk
    that does not yet have an embedding, persisting the 768-dimensional
    vector on the chunk row.

    On success (all chunks embedded) the document ``status`` is set to
    ``"Ready"``.  On any Gemini API error — including a missing or invalid
    ``GEMINI_API_KEY`` — the document ``status`` is set to ``"Failed"`` with
    a readable ``failure_reason``; all already-persisted chunks and
    embeddings are retained and no data is deleted.

    The function is independently callable and does not depend on the rq
    job, so it can be unit-tested directly.
    """
    document = db.execute(
        select(Document).where(Document.id == document_id)
    ).scalar_one_or_none()

    if document is None:
        logger.warning("generate_embeddings: document %s not found", document_id)
        return

    chunks = list(
        db.execute(
            select(Chunk)
            .where(Chunk.document_id == document_id)
            .order_by(Chunk.chunk_index)
        ).scalars()
    )

    # No chunks means there is nothing to embed.  Treat this as "all chunks
    # have embeddings" and mark the document Ready so the pipeline does not
    # hang in Processing forever.
    if not chunks:
        document.status = "Ready"
        document.failure_reason = None
        db.commit()
        return

    # --- Read the live embedding model name from Settings ---
    settings = get_current_settings(db)
    model_name = settings.gemini_embedding_model
    model_ref = _normalise_model_name(model_name)

    # --- Validate the API key before making any network call ---
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or not api_key.strip():
        document.status = "Failed"
        document.failure_reason = (
            "Gemini API key (GEMINI_API_KEY) is not configured. "
            "Set the GEMINI_API_KEY environment variable to generate embeddings."
        )
        db.commit()
        logger.error(
            "generate_embeddings: GEMINI_API_KEY missing for document %s", document_id
        )
        return

    # --- Configure the SDK and embed each chunk that lacks an embedding ---
    try:
        genai.configure(api_key=api_key.strip())

        for chunk in chunks:
            # Skip chunks that already have an embedding so the function is
            # resumable after a partial failure (AC-036).
            if chunk.embedding is not None:
                continue

            result = genai.embed_content(
                model=model_ref,
                content=chunk.chunk_text,
                task_type="RETRIEVAL_DOCUMENT",
                output_dimensionality=_EMBEDDING_DIMENSION,
            )
            embedding = result["embedding"]

            if not isinstance(embedding, list) or len(embedding) != _EMBEDDING_DIMENSION:
                raise ValueError(
                    f"Expected a {_EMBEDDING_DIMENSION}-dimensional embedding "
                    f"from model '{model_name}', got "
                    f"{len(embedding) if isinstance(embedding, list) else 'non-list'} dimensions."
                )

            chunk.embedding = embedding
            # Persist each embedding immediately so progress is retained
            # even if a later chunk fails (AC-036).
            db.commit()

        # --- All chunks now have embeddings → mark Ready (AC-037) ---
        document.status = "Ready"
        document.failure_reason = None
        db.commit()
        logger.info(
            "generate_embeddings: document %s marked Ready (%d chunks embedded)",
            document_id,
            len(chunks),
        )

    except Exception as exc:  # noqa: BLE001 — pipeline must not crash
        # AC-036: set Failed with a readable reason, retain all data.
        reason = f"Gemini embedding generation failed: {exc}"
        document.status = "Failed"
        document.failure_reason = reason
        db.commit()
        logger.error(
            "generate_embeddings: document %s marked Failed — %s", document_id, reason
        )


def process_document(document_id: uuid.UUID, db: Session) -> None:
    """Background-job entry point for the full processing pipeline.

    Orchestrates extraction → chunking → embedding.  Extraction and
    chunking are owned by sibling tickets (``extraction.py``,
    ``chunking.py``); once they land this function will call them before
    :func:`generate_embeddings`.  Until then it calls the embedding step
    directly so the pipeline is wired end-to-end for the steps that exist.

    The document is expected to have ``status='Processing'`` and its chunks
    already persisted by the chunking step.
    """
    # Extraction and chunking steps will be inserted here by their owning
    # tickets.  The embedding step runs after chunking is complete.
    generate_embeddings(document_id, db)