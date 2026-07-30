import json
import struct
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

PROTOCOL_VERSION = 1
MAX_CONTROL_MESSAGE_BYTES = 16 * 1024
AUDIO_HEADER_BYTES = 20
AUDIO_PAYLOAD_BYTES = 640
MAX_AUDIO_MESSAGE_BYTES = AUDIO_HEADER_BYTES + AUDIO_PAYLOAD_BYTES
_AUDIO_MAGIC = b"SUBA"


class ProtocolErrorCode(StrEnum):
    UNSUPPORTED_VERSION = "unsupported_version"
    INVALID_MESSAGE = "invalid_message"
    INVALID_STATE = "invalid_state"
    MESSAGE_TOO_LARGE = "message_too_large"
    SESSION_NOT_FOUND = "session_not_found"
    SERVER_UNAVAILABLE = "server_unavailable"


class ProtocolValidationError(ValueError):
    def __init__(self, message: str, code: ProtocolErrorCode) -> None:
        super().__init__(message)
        self.code = code


class SessionState(StrEnum):
    IDLE = "idle"
    STARTING = "starting"
    STREAMING = "streaming"
    STOPPING = "stopping"
    STOPPED = "stopped"


@dataclass(frozen=True, slots=True)
class AudioFrame:
    sequence: int
    timestamp_ms: int
    payload: bytes


_TRANSITIONS: dict[SessionState, dict[str, SessionState]] = {
    SessionState.IDLE: {"session.start": SessionState.STARTING},
    SessionState.STARTING: {"session.started": SessionState.STREAMING},
    SessionState.STREAMING: {"session.stop": SessionState.STOPPING},
    SessionState.STOPPING: {"session.stopped": SessionState.STOPPED},
    SessionState.STOPPED: {"session.start": SessionState.STARTING},
}


def _schema_path() -> Path:
    repository_root = Path(__file__).resolve().parents[4]
    return repository_root / "packages/protocol/src/control-message.schema.json"


def _load_validator() -> Draft202012Validator:
    schema = json.loads(_schema_path().read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


_VALIDATOR = _load_validator()


def validate_control_message(raw: str) -> dict[str, Any]:
    if len(raw.encode("utf-8")) > MAX_CONTROL_MESSAGE_BYTES:
        raise ProtocolValidationError(
            "Control message exceeds 16 KiB",
            ProtocolErrorCode.MESSAGE_TOO_LARGE,
        )
    try:
        value: Any = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ProtocolValidationError(
            "Control message is not valid JSON",
            ProtocolErrorCode.INVALID_MESSAGE,
        ) from error

    if (
        isinstance(value, dict)
        and "protocolVersion" in value
        and value["protocolVersion"] != PROTOCOL_VERSION
    ):
        raise ProtocolValidationError(
            "Unsupported protocol version",
            ProtocolErrorCode.UNSUPPORTED_VERSION,
        )

    errors = sorted(_VALIDATOR.iter_errors(value), key=lambda error: list(error.path))
    if errors:
        raise ProtocolValidationError(
            "Control message does not match protocol v1",
            ProtocolErrorCode.INVALID_MESSAGE,
        )
    if not isinstance(value, dict):
        raise ProtocolValidationError(
            "Control message must be an object",
            ProtocolErrorCode.INVALID_MESSAGE,
        )
    return value


def decode_audio_frame(raw: bytes) -> AudioFrame:
    if len(raw) > MAX_AUDIO_MESSAGE_BYTES:
        raise ProtocolValidationError(
            "Audio frame is too large",
            ProtocolErrorCode.MESSAGE_TOO_LARGE,
        )
    if len(raw) != MAX_AUDIO_MESSAGE_BYTES:
        raise ProtocolValidationError(
            "Audio frame has an invalid length",
            ProtocolErrorCode.INVALID_MESSAGE,
        )
    if raw[:4] != _AUDIO_MAGIC:
        raise ProtocolValidationError(
            "Audio frame magic is invalid",
            ProtocolErrorCode.INVALID_MESSAGE,
        )

    version, flags, header_length, sequence, timestamp_ms = struct.unpack_from(
        "<BBHIQ", raw, offset=4
    )
    if version != PROTOCOL_VERSION:
        raise ProtocolValidationError(
            "Unsupported protocol version",
            ProtocolErrorCode.UNSUPPORTED_VERSION,
        )
    if flags != 0 or header_length != AUDIO_HEADER_BYTES:
        raise ProtocolValidationError(
            "Audio frame header is invalid",
            ProtocolErrorCode.INVALID_MESSAGE,
        )
    return AudioFrame(
        sequence=sequence,
        timestamp_ms=timestamp_ms,
        payload=raw[AUDIO_HEADER_BYTES:],
    )


def transition_session(state: SessionState, message_type: str) -> SessionState:
    if message_type == "error" or message_type.startswith("health."):
        return state
    try:
        return _TRANSITIONS[state][message_type]
    except KeyError as error:
        raise ProtocolValidationError(
            f"Message {message_type} is invalid while session is {state}",
            ProtocolErrorCode.INVALID_STATE,
        ) from error
