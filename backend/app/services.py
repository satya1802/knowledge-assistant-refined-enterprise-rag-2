"""The backing services this application is configured to reach.

Each entry maps a service to the environment variable that addresses it. The value
comes from docker-compose.yml through .env.example, so the health check reports
what the running deployment can actually reach.

:func:`get_current_settings` is the runtime accessor that chat, embedding, and
RAG code call to read the live configuration values (cosine threshold, Gemini
model names, cookie-secure flag) from the database at query time.
"""

from __future__ import annotations

import math
import os

import google.generativeai as genai
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Chunk, Citation, Conversation, Document, Message, Settings

SERVICES = {
    "redis-queue": "REDIS_URL",
    "gemini-api": "GEMINI_API_KEY",
}


class GeminiUnavailableError(Exception):
    """Raised when the Gemini API cannot answer a chat question.

    Covers a missing/invalid API key, a quota failure, and any other error
    the ``google.generativeai`` SDK raises during embedding creation or
    answer generation (AC-072). ``app.routers.chat`` catches this and turns
    it into the ``CHAT_GEMINI_UNAVAILABLE`` error response instead of an
    unhandled 500 -- no persisted data is touched when this is raised, so
    documents, chunks, embeddings, chat history, and users remain intact.
    """


# ``chunks.embedding`` is a ``Vector(768)`` column (see app.processing), so
# every question embedding must match that dimension to be compared against it.
_EMBEDDING_DIMENSION = 768

# How many of the highest-scoring chunks to pass to Gemini as context /
# attach as citations (AC-065). Not an acceptance criterion by itself, just a
# sane cap so the prompt and the citation list stay small.
RAG_TOP_K = 5


def configured_services() -> dict[str, bool]:
    """Each service mapped to whether its connection variable is set."""
    return {name: bool(os.getenv(var)) for name, var in SERVICES.items()}


def get_current_settings(db: Session) -> Settings:
    """Return the singleton ``Settings`` row, creating it with defaults if absent.

    Future chat, embedding, and RAG code should call this function at query
    time (not cache the result) so that updates made via ``PATCH /settings``
    take effect immediately without a restart.

    The singleton row is always ``id=1``.  If it does not yet exist -- e.g.
    on a fresh database -- it is inserted with the default values declared on
    the ``Settings`` model, committed, and returned.
    """
    settings = db.execute(select(Settings).where(Settings.id == 1)).scalar_one_or_none()

    if settings is None:
        settings = Settings(id=1)
        db.add(settings)
        db.commit()
        db.refresh(settings)

    return settings


# ---------------------------------------------------------------------------
# RAG chat (US-023): retrieval, grounded answer, citations
# ---------------------------------------------------------------------------


def _normalise_model_name(model_name: str) -> str:
    """Return *model_name* prefixed with ``models/`` if it is not already.

    Mirrors ``app.processing._normalise_model_name``: the ``google.generativeai``
    SDK requires fully qualified model names, while ``Settings`` stores the
    bare name.
    """
    if model_name.startswith("models/"):
        return model_name
    return f"models/{model_name}"


def _require_api_key() -> str:
    """Return the configured Gemini API key, or raise ``GeminiUnavailableError``
    if it is missing (AC-072: surfaced as a clear error, not a crash)."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or not api_key.strip():
        raise GeminiUnavailableError(
            "Gemini API key (GEMINI_API_KEY) is not configured. "
            "Set the GEMINI_API_KEY environment variable to use the RAG chat flow."
        )
    return api_key.strip()


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity of two equal-length vectors; 0.0 if either is a zero vector."""
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def embed_question(question: str, db: Session) -> list[float]:
    """Embed *question* with the live Gemini embedding model (AC-065).

    Reads ``Settings.gemini_embedding_model`` at call time (never cached) so
    a change made via ``PATCH /settings`` applies to the very next question.
    Raises ``GeminiUnavailableError`` when ``GEMINI_API_KEY`` is missing or
    the Gemini API returns an error or quota failure (AC-072); no data is
    written before this can happen, so nothing persisted is at risk.
    """
    settings = get_current_settings(db)
    model_ref = _normalise_model_name(settings.gemini_embedding_model)
    api_key = _require_api_key()

    try:
        genai.configure(api_key=api_key)
        result = genai.embed_content(
            model=model_ref,
            content=question,
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=_EMBEDDING_DIMENSION,
        )
    except GeminiUnavailableError:
        raise
    except Exception as exc:  # noqa: BLE001 — any Gemini SDK error (AC-072)
        raise GeminiUnavailableError(f"Gemini embedding creation failed: {exc}") from exc
    return result["embedding"]


def retrieve_relevant_chunks(
    question_embedding: list[float],
    db: Session,
    *,
    top_k: int = RAG_TOP_K,
) -> list[tuple[Chunk, float]]:
    """Return the ``Chunk`` rows of ``Ready`` documents whose cosine
    similarity to *question_embedding* meets the live
    ``Settings.cosine_threshold``, highest similarity first and capped at
    *top_k* (AC-065).

    Reads the threshold from ``Settings`` at call time and queries the
    persisted ``chunks`` table directly -- there is no in-memory index to
    rebuild, so a question asked after a page refresh or a backend restart
    is answered from the same persisted embeddings (AC-068).
    """
    threshold = get_current_settings(db).cosine_threshold

    rows = db.execute(
        select(Chunk)
        .join(Document, Chunk.document_id == Document.id)
        .where(Document.status == "Ready")
        .where(Chunk.embedding.is_not(None))
    ).scalars()

    scored: list[tuple[Chunk, float]] = []
    for chunk in rows:
        embedding = list(chunk.embedding) if chunk.embedding is not None else None
        if not embedding:
            continue
        score = _cosine_similarity(question_embedding, embedding)
        if score >= threshold:
            scored.append((chunk, score))

    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:top_k]


def _build_context(chunks: list[Chunk]) -> str:
    return "\n\n".join(f"[Source {i + 1}] {chunk.chunk_text}" for i, chunk in enumerate(chunks))


def generate_grounded_answer(question: str, chunks: list[Chunk], db: Session) -> str:
    """Call Gemini with the retrieved *chunks* as context so the answer is
    grounded in them (AC-065) rather than fabricated (AC-067).

    Reads ``Settings.gemini_answer_model`` at call time. Raises
    ``GeminiUnavailableError`` on any Gemini API error or quota failure
    (AC-072) rather than letting it crash the request.
    """
    settings = get_current_settings(db)
    model_ref = _normalise_model_name(settings.gemini_answer_model)
    api_key = _require_api_key()

    prompt = (
        "You are a knowledge-base assistant. Answer the question using ONLY "
        "the context below, which was retrieved from the user's uploaded "
        "documents. Do not use outside knowledge and do not invent sources. "
        "If the context does not contain the answer, say so plainly.\n\n"
        f"Context:\n{_build_context(chunks)}\n\n"
        f"Question: {question}\n\nAnswer:"
    )

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_ref)
        response = model.generate_content(prompt)
    except GeminiUnavailableError:
        raise
    except Exception as exc:  # noqa: BLE001 — any Gemini SDK error (AC-072)
        raise GeminiUnavailableError(f"Gemini answer generation failed: {exc}") from exc
    return response.text


def generate_fallback_answer(question: str, db: Session) -> str:
    """Call Gemini with no retrieved context (no chunk met the cosine
    threshold). Used for the fallback branch of AC-065; callers attach no
    citations to a fallback answer (AC-067). Raises ``GeminiUnavailableError``
    on any Gemini API error or quota failure (AC-072).
    """
    settings = get_current_settings(db)
    model_ref = _normalise_model_name(settings.gemini_answer_model)
    api_key = _require_api_key()

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_ref)
        response = model.generate_content(question)
    except GeminiUnavailableError:
        raise
    except Exception as exc:  # noqa: BLE001 — any Gemini SDK error (AC-072)
        raise GeminiUnavailableError(f"Gemini fallback answer generation failed: {exc}") from exc
    return response.text


def answer_chat_question(conversation: Conversation, question: str, db: Session) -> Message:
    """Run the full RAG flow for *question* in *conversation* and persist it.

    Persists the user's question as a ``Message``, retrieves the chunks of
    ``Ready`` documents whose cosine similarity to the question meets the
    live threshold (AC-068: read from the persisted index, not an in-memory
    cache), asks Gemini for a grounded answer when any are found (AC-065),
    or an un-grounded fallback answer when none are (AC-067: no citations
    attached to a fallback answer), persists the assistant's ``Message`` and
    its ``Citation`` rows, and returns the assistant ``Message`` with
    ``citations`` eagerly loaded.

    Raises ``GeminiUnavailableError`` when the Gemini API returns an error or
    quota failure while embedding the question or generating the answer
    (AC-072); nothing is committed in that case, so no partial message or
    citation is left behind and every already-persisted row is untouched.
    """
    db.add(Message(conversation_id=conversation.id, role="user", content=question))
    db.flush()

    question_embedding = embed_question(question, db)
    scored_chunks = retrieve_relevant_chunks(question_embedding, db)

    chunks = [chunk for chunk, _score in scored_chunks]

    if chunks:
        answer_text = generate_grounded_answer(question, chunks, db)
        is_fallback = False
    else:
        answer_text = generate_fallback_answer(question, db)
        is_fallback = True

    assistant_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=answer_text,
        is_fallback=is_fallback,
    )
    db.add(assistant_message)
    db.flush()

    if not is_fallback:
        for chunk in chunks:
            db.add(
                Citation(
                    message_id=assistant_message.id,
                    document_id=chunk.document_id,
                    chunk_id=chunk.id,
                    filename=chunk.document.filename,
                    page_section=chunk.page_section,
                )
            )
        db.flush()

    db.commit()
    db.refresh(assistant_message)
    return assistant_message
