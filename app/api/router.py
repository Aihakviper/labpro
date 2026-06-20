from fastapi import APIRouter

from app.api.routes import auth, health
from app.core.config import get_settings

settings = get_settings()

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router, prefix=f"{settings.api_v1_prefix}/auth", tags=["auth"])

