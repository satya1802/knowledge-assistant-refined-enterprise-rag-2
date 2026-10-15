"""Generated routers: one per architecture component that owns endpoints."""

from app.routers.auth import router as auth_router
from app.routers.chat import router as chat_router
from app.routers.conversations import router as conversations_router
from app.routers.documents import router as documents_router
from app.routers.settings import router as settings_router
from app.routers.users import router as users_router

__all__ = [
    "auth_router",
    "chat_router",
    "conversations_router",
    "documents_router",
    "settings_router",
    "users_router",
]
