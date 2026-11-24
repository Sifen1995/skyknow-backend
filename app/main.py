from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.composition.database import close_database
from app.composition.redis import close_redis
from app.config import settings
from app.core.errors import register_error_handlers
from app.core.logging import setup_logging
from app.core.middleware import RequestIDMiddleware, SecurityHeadersMiddleware
from app.routers.health import router as health_router
from app.routers.identity import router as identity_router
from app.routers.platform_admin import router as platform_admin_router
from app.routers.security import require_authenticated_user
from app.routers.tenants import router as tenants_router

public_router = APIRouter()
public_router.include_router(health_router)
public_router.include_router(platform_admin_router, prefix=settings.API_V1_STR)
public_router.include_router(tenants_router, prefix=settings.API_V1_STR)
public_router.include_router(identity_router, prefix=settings.API_V1_STR)

secured_router = APIRouter(dependencies=[Depends(require_authenticated_user)])


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logging()
    try:
        yield
    finally:
        await close_redis()
        await close_database()


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Tenant-Subdomain",
        "X-Tenant",
        "X-Request-ID",
    ],
)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
register_error_handlers(app)


app.include_router(public_router)
app.include_router(secured_router)

# Mount static assets for local dev fallback (in production, NGINX intercepts /assets/ directly)
try:
    Path(settings.ASSETS_STORAGE_DIR).mkdir(parents=True, exist_ok=True)
    app.mount(
        "/assets", StaticFiles(directory=settings.ASSETS_STORAGE_DIR), name="assets"
    )
except OSError:
    pass
