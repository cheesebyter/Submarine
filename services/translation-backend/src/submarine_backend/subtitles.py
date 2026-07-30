import asyncio
import contextlib
import json
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from submarine_backend.protocol import (
    ProtocolErrorCode,
    ProtocolValidationError,
    validate_control_message,
)

StopCallback = Callable[[str], Awaitable[None]]
ConfigureCallback = Callable[[str | None], None]
_HELLO_TIMEOUT_SECONDS = 5.0


class SubtitleCapacityError(RuntimeError):
    """Raised when the bounded subtitle connection pool is full."""


class SubtitleHub:
    """Fan out ephemeral session events without retaining transcript text."""

    def __init__(
        self,
        *,
        queue_capacity: int = 32,
        max_connections: int = 4,
    ) -> None:
        if queue_capacity < 1:
            raise ValueError("queue_capacity must be positive")
        if max_connections < 1:
            raise ValueError("max_connections must be positive")
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._queue_capacity = queue_capacity
        self._max_connections = max_connections
        self._connection_count = 0
        self._active_session_id: str | None = None
        self._stop_callback: StopCallback | None = None
        self._configure_callback: ConfigureCallback | None = None

    @property
    def active_session_id(self) -> str | None:
        return self._active_session_id

    @property
    def connection_count(self) -> int:
        return self._connection_count

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    def reserve_connection(self) -> None:
        if self._connection_count >= self._max_connections:
            raise SubtitleCapacityError("Subtitle connection capacity reached")
        self._connection_count += 1

    def release_connection(self) -> None:
        if self._connection_count < 1:
            raise RuntimeError("Subtitle connection reservation underflow")
        self._connection_count -= 1

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(self._queue_capacity)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers.discard(queue)

    async def publish(self, message: dict[str, Any]) -> None:
        for queue in tuple(self._subscribers):
            if queue.full():
                with contextlib.suppress(asyncio.QueueEmpty):
                    queue.get_nowait()
                    queue.task_done()
            queue.put_nowait(message)

    async def register_capture(
        self,
        session_id: str,
        stop_callback: StopCallback,
        configure_callback: ConfigureCallback,
        started_message: dict[str, Any],
    ) -> None:
        self._active_session_id = session_id
        self._stop_callback = stop_callback
        self._configure_callback = configure_callback
        await self.publish(started_message)

    async def unregister_capture(
        self,
        session_id: str,
        stopped_message: dict[str, Any] | None = None,
    ) -> None:
        if self._active_session_id != session_id:
            return
        self._active_session_id = None
        self._stop_callback = None
        self._configure_callback = None
        if stopped_message is not None:
            await self.publish(stopped_message)

    async def stop_capture(self, session_id: str) -> None:
        if self._active_session_id != session_id or self._stop_callback is None:
            raise ProtocolValidationError(
                "The capture session is no longer active",
                ProtocolErrorCode.SESSION_NOT_FOUND,
            )
        await self._stop_callback("user")

    def configure_capture(self, session_id: str, language: str | None) -> None:
        if self._active_session_id != session_id or self._configure_callback is None:
            raise ProtocolValidationError(
                "The capture session is no longer active",
                ProtocolErrorCode.SESSION_NOT_FOUND,
            )
        self._configure_callback(language)


async def subtitle_websocket(websocket: WebSocket) -> None:
    if websocket.headers.get("origin"):
        await websocket.close(code=1008, reason="Browser origins are not allowed")
        return

    hub: SubtitleHub = websocket.app.state.subtitle_hub
    try:
        hub.reserve_connection()
    except SubtitleCapacityError:
        await websocket.close(code=1013, reason="Subtitle connection capacity reached")
        return

    queue: asyncio.Queue[dict[str, Any]] | None = None
    sender: asyncio.Task[None] | None = None
    try:
        await websocket.accept()
        raw = await asyncio.wait_for(
            websocket.receive_text(),
            timeout=_HELLO_TIMEOUT_SECONDS,
        )
        hello = validate_control_message(raw)
        if hello["type"] != "hello" or hello["clientType"] != "subtitle":
            raise ProtocolValidationError(
                "A subtitle hello must be the first message",
                ProtocolErrorCode.INVALID_STATE,
            )
        queue = hub.subscribe()

        engine = websocket.app.state.translation_engine
        health = {
            "type": "health.response",
            "protocolVersion": 1,
            "requestId": hello["requestId"],
            "status": "ready" if engine.ready else "degraded",
        }
        await websocket.send_text(json.dumps(health, separators=(",", ":")))
        if hub.active_session_id is not None:
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "session.started",
                        "protocolVersion": 1,
                        "requestId": hello["requestId"],
                        "sessionId": hub.active_session_id,
                    },
                    separators=(",", ":"),
                )
            )

        sender = asyncio.create_task(_send_events(websocket, queue))
        while True:
            message = validate_control_message(await websocket.receive_text())
            if message["type"] == "session.stop":
                await hub.stop_capture(str(message["sessionId"]))
            elif message["type"] == "session.configure":
                language = message["sourceLanguage"]
                hub.configure_capture(
                    str(message["sessionId"]),
                    str(language) if language is not None else None,
                )
            else:
                raise ProtocolValidationError(
                    "Only session.stop and session.configure are accepted",
                    ProtocolErrorCode.INVALID_STATE,
                )
    except WebSocketDisconnect:
        return
    except TimeoutError:
        with contextlib.suppress(RuntimeError):
            await websocket.close(code=1008, reason="Subtitle hello timed out")
    except ProtocolValidationError as error:
        with contextlib.suppress(RuntimeError):
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "error",
                        "protocolVersion": 1,
                        "code": error.code.value,
                        "message": str(error),
                        "recoverable": True,
                    },
                    separators=(",", ":"),
                )
            )
        with contextlib.suppress(RuntimeError):
            await websocket.close(code=1008, reason=error.code.value)
    finally:
        if queue is not None:
            hub.unsubscribe(queue)
        hub.release_connection()
        if sender is not None:
            sender.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await sender


async def _send_events(
    websocket: WebSocket,
    queue: asyncio.Queue[dict[str, Any]],
) -> None:
    while True:
        message = await queue.get()
        try:
            await websocket.send_text(json.dumps(message, separators=(",", ":")))
        finally:
            queue.task_done()
