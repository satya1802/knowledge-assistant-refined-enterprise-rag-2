"""Application entrypoint.

Generated from the approved architecture: one router per component that owns
endpoints, one route per endpoint the API spec declares. Every generated route
is a stub that returns a typed placeholder, so the service starts, serves its
OpenAPI document and passes its tests before a single handler is implemented.
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models  # noqa: F401 -- imported so the tables register before create_all
from app.database import Base, engine
from app.services import configured_services

app = FastAPI(
    title="Knowledge Assistant Refined Enterprise RAG (2)",
    description="Knowledge Assistant Refined Enterprise RAG Chatbot - Gemini-Only Persistent Knowledge Base Build Specification AI Provider Google Gemini API only Primary Source Persisted uploaded Knowledge Base Fallback Gemini general knowledge only after Knowledge Base retrieval finds no relevant match Persistence Documents, files, chunks, embeddings, users, chats and settings survive reloads/restarts Admin Login satya.ganaraju@quorq.ai Reference Stack FastAPI + React/TypeScript + SQLite local / PostgreSQL + pgvector production Core rule: Upload once, persist permanently until explicit deletion, index the document, and search the persisted Knowledge Base before every knowledge answer. Page refresh, logout/login, browser reopen, backend restart, or normal application restart must not erase uploaded documents or chat history. 1. Product Goal Build an enterprise RAG chatbot called Knowledge Assistant. Authorized users upload company documents into a shared Knowledge Base. The application permanently stores the uploaded file and its database records, processes and indexes it, and then uses that indexed content as the first source for chatbot answers. Google Gemini is the only AI provider. Do not configure, request, install, reference, or fall back to Groq or any Groq API key, model, SDK, embedding provider, environment variable, or integration. 2. Mandatory Admin Credentials Create/seed the following administrator account for the MVP: Username / Email: satya.ganaraju@quorq.ai Initial Password: admin@123 Role: Administrator Store the password as a bcrypt hash in the database; never store or log the plaintext password. The plaintext value above is only the required initial login credential. The user must be able to change the password after sign-in. 3. Gemini API Configuration - Only Use a Google Gemini API key only. Store it server-side in a gitignored backend/.env file or a secure runtime secret. Never expose it to React/browser code and never log it.",
    version="0.1.0",
)

# The SPA runs on a different origin than the API, so the browser refuses its calls
# unless that origin is allowed here. In development that is the Vite dev server; when
# deployed, the platform injects the frontend's real URL as ALLOWED_ORIGINS (comma
# separated). Point ALLOWED_ORIGINS at the real thing and nothing else has to change.
_dev_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
_allowed_origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins or _dev_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# The scaffold ships no migrations, so the tables are created from the models on
# startup. Replace this with Alembic before anything holds data worth keeping.
Base.metadata.create_all(bind=engine)


@app.get("/health")
async def health() -> dict[str, object]:
    """Liveness probe, and the only route here that is not a stub."""
    return {"status": "ok", "services": configured_services()}
