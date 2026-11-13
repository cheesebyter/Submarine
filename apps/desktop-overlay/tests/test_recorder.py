from datetime import datetime
from pathlib import Path

from submarine_overlay.recorder import MISSING_ORIGINAL, TranscriptRecorder
from submarine_overlay.settings import LANGUAGES, load_settings, save_settings


def _recorder(directory: Path) -> TranscriptRecorder:
    return TranscriptRecorder(directory, clock=lambda: datetime(2026, 11, 12, 12, 30, 5))


def test_inactive_recorder_writes_nothing(tmp_path: Path) -> None:
    recorder = _recorder(tmp_path)
    assert recorder.record("Hello.", "Hallo.") is False
    assert list(tmp_path.iterdir()) == []


def test_recording_writes_two_aligned_files_lazily(tmp_path: Path) -> None:
    recorder = _recorder(tmp_path)
    recorder.start()
    assert list(tmp_path.iterdir()) == []

    assert recorder.record("Good morning.", "Guten Morgen.") is True
    assert recorder.record("How are you?", None) is True
    recorder.stop()

    original = (tmp_path / "20261112-123005_original.txt").read_text(encoding="utf-8")
    english = (tmp_path / "20261112-123005_english.txt").read_text(encoding="utf-8")
    assert original.splitlines() == ["Guten Morgen.", MISSING_ORIGINAL]
    assert english.splitlines() == ["Good morning.", "How are you?"]


def test_adjacent_duplicates_and_empty_segments_are_skipped(tmp_path: Path) -> None:
    recorder = _recorder(tmp_path)
    recorder.start()
    assert recorder.record("Thank you.", "Danke.") is True
    assert recorder.record("thank you", "Danke") is False
    assert recorder.record("   ", "x") is False
    recorder.stop()
    assert (tmp_path / "20261112-123005_english.txt").read_text(encoding="utf-8") == "Thank you.\n"


def test_multiline_text_is_collapsed_and_stop_disarms(tmp_path: Path) -> None:
    recorder = _recorder(tmp_path)
    recorder.start()
    recorder.record("Line one\nline two", "Zeile eins\nZeile zwei")
    recorder.stop()
    assert recorder.active is False
    assert recorder.record("More.", "Mehr.") is False
    english = (tmp_path / "20261112-123005_english.txt").read_text(encoding="utf-8")
    assert english == "Line one line two\n"


def test_settings_roundtrip_and_fallback(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    assert load_settings(path)[0] == "Auto"
    save_settings("German", tmp_path / "out", path)
    assert load_settings(path) == ("German", tmp_path / "out")
    path.write_text('{"language": "Klingon"}', encoding="utf-8")
    assert load_settings(path)[0] == "Auto"
    assert LANGUAGES["German"] == "de"
