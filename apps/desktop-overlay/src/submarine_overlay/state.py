import re
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class OverlayState:
    connected: bool = False
    model_status: str = "checking"
    capture_status: str = "waiting"
    session_id: str | None = None
    source_language: str | None = None
    provisional: str = ""
    finals: deque[str] = field(default_factory=lambda: deque(maxlen=6))
    error: str | None = None
    audio_rms: float = 0.0
    last_audio_at: float | None = None
    last_signal_at: float | None = None

    def apply(self, message: dict[str, Any]) -> None:
        message_type = message.get("type")
        if message_type == "health.response":
            self.connected = True
            self.model_status = str(message.get("status", "degraded"))
            self.error = None
        elif message_type == "session.started":
            self.capture_status = "capturing"
            self.session_id = str(message["sessionId"])
        elif message_type == "session.stopped":
            self.capture_status = "stopped"
            self.session_id = None
            self.provisional = ""
        elif message_type == "transcript.provisional":
            self.provisional = str(message["text"])
            self.source_language = _language(message.get("sourceLanguage"))
        elif message_type == "transcript.final":
            text = str(message["text"]).strip()
            self.provisional = ""
            if text and (
                not self.finals
                or _normalized_transcript(self.finals[-1]) != _normalized_transcript(text)
            ):
                self.finals.append(text)
            self.source_language = _language(message.get("sourceLanguage"))
        elif message_type == "error":
            self.error = str(message.get("message", "Unknown local service error"))
        elif message_type == "audio.level":
            now = time.monotonic()
            self.audio_rms = float(message.get("rms", 0.0))
            self.last_audio_at = now
            if message.get("signal") is True:
                self.last_signal_at = now

    def disconnected(self) -> None:
        self.connected = False
        self.capture_status = "waiting"
        self.session_id = None
        self.audio_rms = 0.0

    def has_no_signal(self, now: float | None = None) -> bool:
        if self.capture_status != "capturing" or self.last_audio_at is None:
            return False
        current = time.monotonic() if now is None else now
        reference = self.last_signal_at or self.last_audio_at
        return current - reference >= 3.0

    def clear_transcript(self) -> None:
        self.finals.clear()
        self.provisional = ""


def _language(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _normalized_transcript(text: str) -> str:
    return re.sub(r"[^\w]+", " ", text, flags=re.UNICODE).strip().casefold()
