import asyncio
import contextlib
import json
import re
import secrets
from dataclasses import dataclass
from typing import Any, Literal

from fastapi import WebSocket, WebSocketDisconnect

from submarine_backend.protocol import (
    ProtocolErrorCode,
    ProtocolValidationError,
    SessionState,
    decode_audio_frame,
    transition_session,
    validate_control_message,
)
from submarine_backend.translation import TranslationResult, TranslationSession, pcm_rms

_CHROME_EXTENSION_ORIGIN = re.compile(r"^chrome-extension://[a-p]{32}$")


@dataclass(slots=True)
class CaptureSession:
    state: SessionState = SessionState.IDLE
    hello_received: bool = False
    session_id: str | None = None
    translation: TranslationSession | None = None
    send_lock: asyncio.Lock | None = None
    audio_frames: int = 0


async def capture_websocket(
    websocket: WebSocket,
    *,
    require_extension_origin: bool = True,
) -> None:
    origin = websocket.headers.get("origin", "")
    if require_extension_origin and _CHROME_EXTENSION_ORIGIN.fullmatch(origin) is None:
        await websocket.close(code=1008, reason="Chrome extension origin required")
        return
    if not require_extension_origin and origin:
        await websocket.close(code=1008, reason="Native clients must not send an origin")
        return

    await websocket.accept()
    session = CaptureSession()
    session.send_lock = asyncio.Lock()
    try:
        while True:
            event = await websocket.receive()
            if event["type"] == "websocket.disconnect":
                return
            if text := event.get("text"):
                should_close = await _handle_control(websocket, session, text)
                if should_close:
                    return
            elif data := event.get("bytes"):
                level = _handle_audio(session, data)
                if level is not None:
                    await websocket.app.state.subtitle_hub.publish(level)
    except WebSocketDisconnect:
        return
    except ProtocolValidationError as error:
        await _send_error(websocket, error)
        await websocket.close(code=1008, reason=error.code.value)
    finally:
        if session.translation is not None:
            await session.translation.cancel()
        if session.session_id is not None:
            await websocket.app.state.subtitle_hub.unregister_capture(session.session_id)


async def _handle_control(
    websocket: WebSocket,
    session: CaptureSession,
    raw: str,
) -> bool:
    message = validate_control_message(raw)
    message_type = str(message["type"])

    if message_type == "hello":
        if session.hello_received:
            raise ProtocolValidationError(
                "Hello was already received",
                ProtocolErrorCode.INVALID_STATE,
            )
        session.hello_received = True
        return False

    if not session.hello_received:
        raise ProtocolValidationError(
            "Hello must be the first message",
            ProtocolErrorCode.INVALID_STATE,
        )

    if message_type == "session.start":
        engine = websocket.app.state.translation_engine
        if not engine.ready:
            raise ProtocolValidationError(
                f"Local translation model is not ready: {engine.status}",
                ProtocolErrorCode.SERVER_UNAVAILABLE,
            )
        session.state = transition_session(session.state, message_type)
        session.session_id = secrets.token_urlsafe(24)

        async def on_result(
            kind: Literal["provisional", "final"],
            sequence: int,
            result: TranslationResult,
        ) -> None:
            response = {
                "type": f"transcript.{kind}",
                "protocolVersion": 1,
                "sessionId": session.session_id,
                "sequence": sequence,
                "text": result.text,
                "sourceLanguage": result.source_language,
            }
            await _send_json(websocket, session, response)
            await websocket.app.state.subtitle_hub.publish(response)

        async def on_translation_error(error_name: str) -> None:
            await _send_error_message(
                websocket,
                code=ProtocolErrorCode.SERVER_UNAVAILABLE,
                message=f"Local translation failed: {error_name}",
                recoverable=True,
            )

        session.translation = TranslationSession(
            engine,
            on_result,
            on_translation_error,
            cleaner=websocket.app.state.ollama_cleaner_factory(),
        )
        response = {
            "type": "session.started",
            "protocolVersion": 1,
            "requestId": message["requestId"],
            "sessionId": session.session_id,
        }
        await _send_json(websocket, session, response)
        session.state = transition_session(session.state, "session.started")
        session.translation.start()

        async def stop_capture(reason: str) -> None:
            if session.translation is not None:
                await session.translation.finish()
                session.translation = None
            stopped = {
                "type": "session.stopped",
                "protocolVersion": 1,
                "sessionId": session.session_id,
                "reason": reason,
            }
            await websocket.app.state.subtitle_hub.unregister_capture(
                str(session.session_id), stopped
            )
            with contextlib.suppress(RuntimeError):
                await _send_json(websocket, session, stopped)
            with contextlib.suppress(RuntimeError):
                await websocket.close(code=1000, reason="Session stopped")

        await websocket.app.state.subtitle_hub.register_capture(
            str(session.session_id),
            stop_capture,
            session.translation.set_source_language,
            response,
        )
        return False

    if message_type == "session.stop":
        if message["sessionId"] != session.session_id:
            raise ProtocolValidationError(
                "Session does not exist",
                ProtocolErrorCode.INVALID_STATE,
            )
        session.state = transition_session(session.state, message_type)
        if session.translation is not None:
            await session.translation.finish()
            session.translation = None
        response = {
            "type": "session.stopped",
            "protocolVersion": 1,
            "sessionId": session.session_id,
            "reason": message["reason"],
        }
        await _send_json(websocket, session, response)
        await websocket.app.state.subtitle_hub.unregister_capture(str(session.session_id), response)
        session.state = transition_session(session.state, "session.stopped")
        await websocket.close(code=1000, reason="Session stopped")
        return True

    raise ProtocolValidationError(
        f"Message {message_type} is invalid for a capture connection",
        ProtocolErrorCode.INVALID_STATE,
    )


def _handle_audio(session: CaptureSession, raw: bytes) -> dict[str, Any] | None:
    if session.state != SessionState.STREAMING:
        raise ProtocolValidationError(
            "Audio is only accepted during an active session",
            ProtocolErrorCode.INVALID_STATE,
        )
    frame = decode_audio_frame(raw)
    if session.translation is None:
        raise ProtocolValidationError(
            "Translation session is not running",
            ProtocolErrorCode.INVALID_STATE,
        )
    session.translation.push(frame.payload)
    session.audio_frames += 1
    if session.audio_frames % 25 != 0:
        return None
    rms = min(1.0, pcm_rms(frame.payload))
    return {
        "type": "audio.level",
        "protocolVersion": 1,
        "sessionId": session.session_id,
        "rms": rms,
        "signal": rms >= 0.002,
    }


async def _send_error(websocket: WebSocket, error: ProtocolValidationError) -> None:
    await _send_error_message(
        websocket,
        code=error.code,
        message=str(error),
        recoverable=error.code == ProtocolErrorCode.SERVER_UNAVAILABLE,
    )


async def _send_error_message(
    websocket: WebSocket,
    *,
    code: ProtocolErrorCode,
    message: str,
    recoverable: bool,
) -> None:
    response: dict[str, Any] = {
        "type": "error",
        "protocolVersion": 1,
        "code": code.value,
        "message": message,
        "recoverable": recoverable,
    }
    await websocket.send_text(json.dumps(response, separators=(",", ":")))


async def _send_json(
    websocket: WebSocket,
    session: CaptureSession,
    message: dict[str, Any],
) -> None:
    if session.send_lock is None:
        raise RuntimeError("Capture send lock is not initialized")
    async with session.send_lock:
        await websocket.send_text(json.dumps(message, separators=(",", ":")))
