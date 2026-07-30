import json
import socket
import struct
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
import uvicorn
import websockets

from submarine_backend.main import create_app
from submarine_backend.protocol import AUDIO_HEADER_BYTES, AUDIO_PAYLOAD_BYTES
from submarine_backend.translation import (
    ModelStatus,
    TranslationEngine,
    TranslationResult,
)

ALLOWED_ORIGIN = f"chrome-extension://{'a' * 32}"


class StubTranslationEngine(TranslationEngine):
    @property
    def status(self) -> ModelStatus:
        return ModelStatus.READY

    async def load(self) -> None:
        return

    def translate(self, pcm_s16le: bytes) -> TranslationResult:
        return TranslationResult(
            text="Hello.",
            source_language="es",
            language_probability=0.99,
            inference_ms=1.0,
        )


app = create_app(StubTranslationEngine())


def _free_loopback_port() -> int:
    with socket.socket() as server_socket:
        server_socket.bind(("127.0.0.1", 0))
        return int(server_socket.getsockname()[1])


@contextmanager
def _running_server() -> Iterator[int]:
    port = _free_loopback_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 5
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.01)
    if not server.started:
        raise RuntimeError("Test server did not start")
    try:
        yield port
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        if thread.is_alive():
            raise RuntimeError("Test server did not stop")


def _message(message_type: str, **values: Any) -> str:
    return json.dumps({"type": message_type, "protocolVersion": 1, **values})


def _audio_frame(*, sequence: int = 0, amplitude: int = 0) -> bytes:
    sample = int(amplitude).to_bytes(2, "little", signed=True)
    payload = sample * (AUDIO_PAYLOAD_BYTES // 2)
    return (
        b"SUBA" + struct.pack("<BBHIQ", 1, 0, AUDIO_HEADER_BYTES, sequence, sequence * 20) + payload
    )


@pytest.mark.asyncio
async def test_capture_session_accepts_and_translates_audio_end_to_end() -> None:
    with _running_server() as port:
        async with websockets.connect(
            f"ws://127.0.0.1:{port}/ws/capture",
            origin=ALLOWED_ORIGIN,
        ) as websocket:
            await websocket.send(_message("hello", clientType="capture", requestId="request_1"))
            await websocket.send(
                _message(
                    "session.start",
                    requestId="request_1",
                    audioFormat={
                        "encoding": "pcm_s16le",
                        "sampleRateHz": 16000,
                        "channels": 1,
                        "frameDurationMs": 20,
                    },
                )
            )
            started = json.loads(await websocket.recv())
            assert started["type"] == "session.started"

            for sequence in range(20):
                await websocket.send(_audio_frame(sequence=sequence, amplitude=4000))
            for sequence in range(20, 50):
                await websocket.send(_audio_frame(sequence=sequence))

            transcript = json.loads(await websocket.recv())
            assert transcript == {
                "type": "transcript.final",
                "protocolVersion": 1,
                "sessionId": started["sessionId"],
                "sequence": 0,
                "text": "Hello.",
                "sourceLanguage": "es",
            }

            await websocket.send(
                _message(
                    "session.stop",
                    sessionId=started["sessionId"],
                    reason="user",
                )
            )
            stopped = json.loads(await websocket.recv())
            assert stopped == {
                "type": "session.stopped",
                "protocolVersion": 1,
                "sessionId": started["sessionId"],
                "reason": "user",
            }


@pytest.mark.asyncio
async def test_capture_receiver_rejects_non_extension_origin() -> None:
    with (
        _running_server() as port,
        pytest.raises(websockets.exceptions.InvalidStatus),
    ):
        async with websockets.connect(
            f"ws://127.0.0.1:{port}/ws/capture",
            origin="https://example.com",
        ):
            pass


@pytest.mark.asyncio
async def test_capture_receiver_rejects_audio_before_session() -> None:
    with _running_server() as port:
        async with websockets.connect(
            f"ws://127.0.0.1:{port}/ws/capture",
            origin=ALLOWED_ORIGIN,
        ) as websocket:
            await websocket.send(_audio_frame())
            error = json.loads(await websocket.recv())
            assert error["code"] == "invalid_state"


@pytest.mark.asyncio
async def test_native_capture_accepts_originless_local_client() -> None:
    with _running_server() as port:
        async with websockets.connect(
            f"ws://127.0.0.1:{port}/ws/native-capture",
        ) as websocket:
            await websocket.send(_message("hello", clientType="capture", requestId="native_1"))
            await websocket.send(
                _message(
                    "session.start",
                    requestId="native_1",
                    audioFormat={
                        "encoding": "pcm_s16le",
                        "sampleRateHz": 16000,
                        "channels": 1,
                        "frameDurationMs": 20,
                    },
                )
            )
            started = json.loads(await websocket.recv())
            assert started["type"] == "session.started"
