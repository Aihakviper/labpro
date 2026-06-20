from fastapi import APIRouter

from app.api.routes import (
    auth,
    books,
    fines,
    health,
    loans,
    members,
    reservations,
    users,
)
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
api_router.include_router(
    loans.router,
    prefix=f"{settings.api_v1_prefix}/loans",
    tags=["loans"],
)
api_router.include_router(
    fines.router,
    prefix=f"{settings.api_v1_prefix}/fines",
    tags=["fines"],
)
api_router.include_router(
    reservations.router,
    prefix=f"{settings.api_v1_prefix}/reservations",
    tags=["reservations"],
)
