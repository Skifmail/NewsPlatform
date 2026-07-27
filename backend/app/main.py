"""Точка входа FastAPI."""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import analytics, ai_usage, auth, channels, history, jobs, logs, media, overview, posts, raw_posts, settings as settings_router
from app.api.routers import prompts, sources, vk_oauth
from app.api.websocket import router as ws_router, start_redis_listener
from app.core.config import get_settings
from app.core.logging import setup_logging


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Lifecycle: логирование и Redis listener."""
    setup_logging()
    start_redis_listener()
    yield


def create_app() -> FastAPI:
    """Создаёт и настраивает FastAPI-приложение.

    Returns:
        FastAPI: приложение.
    """
    settings = get_settings()
    application = FastAPI(
        title="AI Content Platform",
        description="Платформа сбора, AI-переработки и публикации контента",
        version="1.0.0",
        lifespan=lifespan,
    )

    _default_origins = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8080",
    ]
    _extra_origins = [
        origin.strip()
        for origin in settings.cors_origins.split(",")
        if origin.strip()
    ]
    application.add_middleware(
        CORSMiddleware,
        allow_origins=_default_origins + _extra_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(media.router, prefix="/api")
    application.include_router(auth.router, prefix="/api")
    application.include_router(jobs.router, prefix="/api")
    application.include_router(logs.router, prefix="/api")
    application.include_router(sources.router, prefix="/api")
    application.include_router(channels.router, prefix="/api")
    application.include_router(posts.router, prefix="/api")
    application.include_router(raw_posts.router, prefix="/api")
    application.include_router(settings_router.router, prefix="/api")
    application.include_router(ai_usage.router, prefix="/api")
    application.include_router(history.router, prefix="/api")
    application.include_router(analytics.router, prefix="/api")
    application.include_router(overview.router, prefix="/api")
    application.include_router(prompts.router, prefix="/api")
    application.include_router(vk_oauth.router, prefix="/api")
    application.include_router(ws_router, prefix="/ws")

    @application.get("/health")
    async def health() -> dict[str, str]:
        """Health check."""
        return {"status": "ok", "debug": str(settings.debug)}

    return application


app = create_app()
