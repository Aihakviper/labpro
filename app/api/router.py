from fastapi import APIRouter

from app.api.routes import auth, books, health, members, users
from app.core.config import get_settings

settings = get_settings()

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router, prefix=f"{settings.api_v1_prefix}/auth", tags=["auth"])
api_router.include_router(users.router, prefix=f"{settings.api_v1_prefix}/users", tags=["users"])
api_router.include_router(
    members.router,
    prefix=f"{settings.api_v1_prefix}/members",
    tags=["members"],
)
api_router.include_router(
    books.router,
    prefix=f"{settings.api_v1_prefix}/books",
    tags=["books"],
)
