import re
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TextIO

MISSING_ORIGINAL = "[Original nicht verfügbar]"


class TranscriptRecorder:
    """Opt-in plain-text recording: one line per final segment in two aligned files."""

    def __init__(
        self,
        directory: Path,
        *,
        clock: Callable[[], datetime] = datetime.now,
    ) -> None:
        self.directory = directory
        self._clock = clock
        self._stamp: str | None = None
        self._original: TextIO | None = None
        self._english: TextIO | None = None
        self._last_english = ""
        self.active = False

    @property
    def original_path(self) -> Path | None:
        return self._path("original")

    @property
    def english_path(self) -> Path | None:
        return self._path("english")

    def start(self) -> None:
        """Arm recording. Files are created lazily with the first final segment."""
        if self.active:
            return
        self._stamp = self._clock().strftime("%Y%m%d-%H%M%S")
        self._last_english = ""
        self.active = True

    def record(self, english: str, original: str | None) -> bool:
        if not self.active:
            return False
        english_line = _single_line(english)
        if not english_line or _normalize(english_line) == self._last_english:
            return False
        if self._original is None or self._english is None:
            self._open()
        assert self._original is not None and self._english is not None
        self._original.write(_single_line(original or "") or MISSING_ORIGINAL)
        self._original.write("\n")
        self._original.flush()
        self._english.write(english_line + "\n")
        self._english.flush()
        self._last_english = _normalize(english_line)
        return True

    def stop(self) -> None:
        for handle in (self._original, self._english):
            if handle is not None:
                handle.close()
        self._original = None
        self._english = None
        self._stamp = None
        self.active = False

    def _path(self, kind: str) -> Path | None:
        if self._stamp is None:
            return None
        return self.directory / f"{self._stamp}_{kind}.txt"

    def _open(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        original_path, english_path = self.original_path, self.english_path
        assert original_path is not None and english_path is not None
        self._original = original_path.open("x", encoding="utf-8", newline="\n")
        try:
            self._english = english_path.open("x", encoding="utf-8", newline="\n")
        except OSError:
            self._original.close()
            self._original = None
            raise


def _single_line(text: str) -> str:
    return " ".join(text.split())


def _normalize(text: str) -> str:
    return re.sub(r"[^\w]+", " ", text, flags=re.UNICODE).strip().casefold()
