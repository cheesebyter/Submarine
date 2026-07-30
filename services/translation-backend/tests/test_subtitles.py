import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from submarine_backend.main import create_app
from submarine_backend.subtitles import SubtitleHub
from submarine_backend.translation import ModelStatus, TranslationEngine, TranslationResult


class ReadyEngine(TranslationEngine):
    @property
    def status(self) -> ModelStatus:
        return ModelStatus.READY

    async def load(self) -> None:
        return

    def translate(self, pcm_s16le: bytes) -> TranslationResult:
        raise AssertionError("Translation is not expected")


def test_subtitle_connection_receives_health_without_persisted_transcript() -> None:
    with (
        TestClient(create_app(ReadyEngine())) as client,
        client.websocket_connect("/ws/subtitles") as socket,
    ):
        socket.send_text(
            json.dumps(
                {
                    "type": "hello",
                    "protocolVersion": 1,
                    "clientType": "subtitle",
                    "requestId": "overlay-1",
                }
            )
        )
        response: dict[str, Any] = socket.receive_json()

    assert response == {
        "type": "health.response",
        "protocolVersion": 1,
        "requestId": "overlay-1",
        "status": "ready",
    }


def test_subtitle_connection_rejects_browser_origin() -> None:
    app = create_app(ReadyEngine())
    hub: SubtitleHub = app.state.subtitle_hub
    client = TestClient(app)

    with (
        client,
        pytest.raises(WebSocketDisconnect) as rejected,
        client.websocket_connect(
            "/ws/subtitles",
            headers={"origin": "https://attacker.example"},
        ),
    ):
        pass

    assert rejected.value.code == 1008
    assert hub.connection_count == 0
    assert hub.subscriber_count == 0


def test_subtitle_connection_does_not_subscribe_before_hello() -> None:
    app = create_app(ReadyEngine())
    hub: SubtitleHub = app.state.subtitle_hub

    with (
        TestClient(app) as client,
        client.websocket_connect("/ws/subtitles"),
    ):
        assert hub.connection_count == 1
        assert hub.subscriber_count == 0

    assert hub.connection_count == 0
    assert hub.subscriber_count == 0


def test_subtitle_connection_times_out_before_hello(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("submarine_backend.subtitles._HELLO_TIMEOUT_SECONDS", 0.01)

    with (
        TestClient(create_app(ReadyEngine())) as client,
        client.websocket_connect("/ws/subtitles") as socket,
        pytest.raises(WebSocketDisconnect) as disconnected,
    ):
        socket.receive_json()

    assert disconnected.value.code == 1008


def test_subtitle_endpoint_bounds_connection_reservations() -> None:
    app = create_app(ReadyEngine())
    hub = SubtitleHub(max_connections=1)
    app.state.subtitle_hub = hub

    with (
        TestClient(app) as client,
        client.websocket_connect("/ws/subtitles"),
    ):
        assert hub.connection_count == 1
        with (
            pytest.raises(WebSocketDisconnect) as rejected,
            client.websocket_connect("/ws/subtitles"),
        ):
            pass
        assert rejected.value.code == 1013
        assert hub.connection_count == 1

    assert hub.connection_count == 0
