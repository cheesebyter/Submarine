import socket
import threading
import time

import httpx
import uvicorn

from submarine_backend.main import create_app
from submarine_backend.translation import (
    ModelStatus,
    TranslationEngine,
    TranslationResult,
)


class StubTranslationEngine(TranslationEngine):
    @property
    def status(self) -> ModelStatus:
        return ModelStatus.READY

    async def load(self) -> None:
        return

    def translate(self, pcm_s16le: bytes) -> TranslationResult:
        return TranslationResult("", None, 0.0, 0.0)


app = create_app(StubTranslationEngine())


def _free_loopback_port() -> int:
    with socket.socket() as server_socket:
        server_socket.bind(("127.0.0.1", 0))
        return int(server_socket.getsockname()[1])


def test_backend_serves_health_over_loopback_tcp() -> None:
    port = _free_loopback_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    try:
        deadline = time.monotonic() + 5
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.01)

        response = httpx.get(f"http://127.0.0.1:{port}/health", timeout=2)
        assert response.status_code == 200
        assert response.json()["status"] == "ready"
    finally:
        server.should_exit = True
        thread.join(timeout=5)

    assert not thread.is_alive()
