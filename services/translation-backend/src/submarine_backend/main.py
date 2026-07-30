from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, WebSocket
from pydantic import BaseModel

from submarine_backend import __version__
from submarine_backend.capture import capture_websocket
from submarine_backend.cleanup import OllamaCleaner
from submarine_backend.config import get_settings
from submarine_backend.subtitles import SubtitleHub, subtitle_websocket
from submarine_backend.translation import (
    FasterWhisperTranslationEngine,
    ModelStatus,
    TranslationEngine,
)


class HealthResponse(BaseModel):
    status: Literal["ready", "loading", "degraded"]
    service: Literal["translation-backend"]
    version: str
    model_status: ModelStatus
    model_name: str
    device: str


def create_app(engine: TranslationEngine | None = None) -> FastAPI:
    settings = get_settings()
    translation_engine = engine or FasterWhisperTranslationEngine(
        settings.model_path.resolve(),
        device=settings.model_device,
        compute_type=settings.model_compute_type,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await translation_engine.load()
        try:
            yield
        finally:
            await translation_engine.close()

    app = FastAPI(
        title="Submarine Translation Backend",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.translation_engine = translation_engine
    app.state.subtitle_hub = SubtitleHub()
    app.state.ollama_cleaner_factory = lambda: OllamaCleaner(
        enabled=settings.ollama_cleanup_enabled,
        url=settings.ollama_url,
        model=settings.ollama_model,
        timeout_seconds=settings.ollama_timeout_seconds,
    )

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        model_status = translation_engine.status
        status: Literal["ready", "loading", "degraded"]
        if model_status == ModelStatus.READY:
            status = "ready"
        elif model_status == ModelStatus.LOADING:
            status = "loading"
        else:
            status = "degraded"
        return HealthResponse(
            status=status,
            service="translation-backend",
            version=__version__,
            model_status=model_status,
            model_name=settings.model_name,
            device=settings.model_device,
        )

    @app.websocket("/ws/capture")
    async def capture(websocket: WebSocket) -> None:
        await capture_websocket(websocket)

    @app.websocket("/ws/native-capture")
    async def native_capture(websocket: WebSocket) -> None:
        await capture_websocket(websocket, require_extension_origin=False)

    @app.websocket("/ws/subtitles")
    async def subtitles(websocket: WebSocket) -> None:
        await subtitle_websocket(websocket)

    return app


app = create_app()
