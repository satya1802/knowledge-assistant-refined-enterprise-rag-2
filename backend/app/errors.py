"""Error codes returned by API endpoints.

Each constant pairs the HTTP status code an endpoint returns with a short,
stable message, so the same failure is described identically everywhere it
occurs and routers import these instead of inlining ad hoc status/detail
pairs. Routes declare them in their ``responses=`` mapping so the exported
OpenAPI document carries the full contract.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorCode:
    status_code: int
    detail: str


# --- Chat (POST /chat) ---

CHAT_EMPTY_QUESTION = ErrorCode(422, "Question must not be empty")
CHAT_CONVERSATION_NOT_FOUND = ErrorCode(404, "Conversation not found")
CHAT_GEMINI_UNAVAILABLE = ErrorCode(
    503,
    "The AI service is temporarily unavailable or has reached its quota. "
    "Your question and chat history have been saved -- please try again shortly.",
)
