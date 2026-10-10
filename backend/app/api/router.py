"""All REST routes under /api/v1 (paths are unchanged from the original API)."""

from fastapi import APIRouter

from app.features.auth.router import router as auth_router
from app.features.conversations.router import router as conversations_router
from app.features.messages.router import router as messages_router
from app.features.system.router import router as system_router
from app.features.translation.router import router as translation_router
from app.features.users.router import router as users_router

API_PREFIX = "/api/v1"

api_router = APIRouter(prefix=API_PREFIX)
for router in (auth_router, users_router, conversations_router, messages_router, translation_router, system_router):
    api_router.include_router(router)
