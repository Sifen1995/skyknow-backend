from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from app.config import settings
from app.core.logging import RequestIDMiddleware, setup_logging
from app.routers.health import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup tasks
    setup_logging()
    yield
    # Shutdown tasks


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# Register Middleware
app.add_middleware(RequestIDMiddleware)

# Include Routers
app.include_router(health_router)