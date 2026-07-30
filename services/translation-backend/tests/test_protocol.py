import json
import struct
from pathlib import Path
from typing import Any

import pytest

from submarine_backend.protocol import (
    AUDIO_HEADER_BYTES,
    AUDIO_PAYLOAD_BYTES,
    MAX_CONTROL_MESSAGE_BYTES,
    ProtocolErrorCode,
    ProtocolValidationError,
    SessionState,
    decode_audio_frame,
    transition_session,
    validate_control_message,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_DIRECTORY = REPOSITORY_ROOT / "packages/protocol/fixtures"


def _fixtures(name: str) -> list[dict[str, Any]]:
    return json.loads((FIXTURE_DIRECTORY / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "fixture", _fixtures("control-messages.json"), ids=lambda item: item["name"]
)
def test_shared_control_message_fixtures(fixture: dict[str, Any]) -> None:
    raw = json.dumps(fixture["message"])
    if fixture["valid"]:
        assert validate_control_message(raw) == fixture["message"]
        return

    with pytest.raises(ProtocolValidationError) as raised:
        validate_control_message(raw)
    assert raised.value.code == fixture["errorCode"]


@pytest.mark.parametrize(
    "fixture",
    _fixtures("state-transitions.json"),
    ids=lambda item: f"{item['state']} + {item['messageType']}",
)
def test_shared_state_transition_fixtures(fixture: dict[str, Any]) -> None:
    state = SessionState(fixture["state"])
    if fixture["valid"]:
        assert transition_session(state, fixture["messageType"]) == fixture["next"]
        return

    with pytest.raises(ProtocolValidationError) as raised:
        transition_session(state, fixture["messageType"])
    assert raised.value.code == ProtocolErrorCode.INVALID_STATE


def test_oversized_control_message_is_rejected() -> None:
    with pytest.raises(ProtocolValidationError) as raised:
        validate_control_message(" " * (MAX_CONTROL_MESSAGE_BYTES + 1))
    assert raised.value.code == ProtocolErrorCode.MESSAGE_TOO_LARGE


def _audio_frame(*, version: int = 1, magic: bytes = b"SUBA") -> bytes:
    header = magic + struct.pack("<BBHIQ", version, 0, AUDIO_HEADER_BYTES, 42, 1234)
    return header + bytes(AUDIO_PAYLOAD_BYTES)


def test_audio_frame_is_decoded() -> None:
    frame = decode_audio_frame(_audio_frame())
    assert frame.sequence == 42
    assert frame.timestamp_ms == 1234
    assert frame.payload == bytes(AUDIO_PAYLOAD_BYTES)


@pytest.mark.parametrize(
    ("raw", "error_code"),
    [
        (_audio_frame(magic=b"NOPE"), ProtocolErrorCode.INVALID_MESSAGE),
        (_audio_frame(version=2), ProtocolErrorCode.UNSUPPORTED_VERSION),
        (_audio_frame() + b"\x00", ProtocolErrorCode.MESSAGE_TOO_LARGE),
        (_audio_frame()[:-1], ProtocolErrorCode.INVALID_MESSAGE),
    ],
)
def test_invalid_audio_frame_is_rejected(raw: bytes, error_code: ProtocolErrorCode) -> None:
    with pytest.raises(ProtocolValidationError) as raised:
        decode_audio_frame(raw)
    assert raised.value.code == error_code
