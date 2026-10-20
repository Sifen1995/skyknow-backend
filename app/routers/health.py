import logging
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    status: str
    environment: str
    version: str


@router.get("/health", response_model=HealthResponse)
async def health_check() -> dict[str, Any]:
    logger.info("Health check ping received")
    return {
        "status": "ok",
        "environment": settings.ENVIRONMENT,
        "version": "0.1.0",
    }