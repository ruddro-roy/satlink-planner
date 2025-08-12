from __future__ import annotations

from fastapi import APIRouter

from core.config import settings

router = APIRouter()


@router.get("/public")
async def get_public_config():
    return {
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "cors": settings.BACKEND_CORS_ORIGINS,
    }


