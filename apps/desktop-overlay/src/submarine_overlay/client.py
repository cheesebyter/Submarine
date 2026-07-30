import asyncio
import json
import queue
import threading
import uuid
from typing import Any

from websockets.asyncio.client import ClientConnection, connect


class OverlayClient:
    def __init__(
        self,
        events: queue.Queue[dict[str, Any]],
        url: str = "ws://127.0.0.1:8765/ws/subtitles",
    ) -> None:
        self.events = events
        self.url = url
        self._stop = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._socket: ClientConnection | None = None
        self._thread = threading.Thread(
            target=self._thread_main,
            name="submarine-overlay-network",
            daemon=True,
        )

    def start(self) -> None:
        self._thread.start()

    def request_capture_stop(self, session_id: str) -> None:
        if self._loop is None or self._socket is None:
            return
        message = {
            "type": "session.stop",
            "protocolVersion": 1,
            "sessionId": session_id,
            "reason": "user",
        }
        asyncio.run_coroutine_threadsafe(
            self._socket.send(json.dumps(message, separators=(",", ":"))),
            self._loop,
        )

    def configure_language(self, session_id: str, language: str | None) -> None:
        if self._loop is None or self._socket is None:
            return
        message = {
            "type": "session.configure",
            "protocolVersion": 1,
            "sessionId": session_id,
            "sourceLanguage": language,
        }
        asyncio.run_coroutine_threadsafe(
            self._socket.send(json.dumps(message, separators=(",", ":"))),
            self._loop,
        )

    def close(self) -> None:
        self._stop.set()
        if self._loop is not None and self._socket is not None:
            asyncio.run_coroutine_threadsafe(self._socket.close(), self._loop)
        self._thread.join(timeout=1.0)

    def _thread_main(self) -> None:
        asyncio.run(self._run())

    async def _run(self) -> None:
        self._loop = asyncio.get_running_loop()
        while not self._stop.is_set():
            try:
                async with connect(
                    self.url,
                    open_timeout=2,
                    close_timeout=1,
                    max_size=16 * 1024,
                ) as socket:
                    self._socket = socket
                    await socket.send(
                        json.dumps(
                            {
                                "type": "hello",
                                "protocolVersion": 1,
                                "clientType": "subtitle",
                                "requestId": uuid.uuid4().hex,
                            },
                            separators=(",", ":"),
                        )
                    )
                    async for raw in socket:
                        if isinstance(raw, str):
                            self.events.put(json.loads(raw))
            except (OSError, TimeoutError):
                self.events.put(
                    {
                        "type": "connection.closed",
                        "message": "Backend nicht erreichbar. Starte scripts/dev-backend.ps1.",
                    }
                )
            except Exception as error:
                self.events.put(
                    {
                        "type": "connection.closed",
                        "message": f"Lokale Verbindung unterbrochen: {type(error).__name__}",
                    }
                )
            finally:
                self._socket = None
            if not self._stop.is_set():
                await asyncio.sleep(2)
