import json
from pathlib import Path

# Overlay -> (display name, Whisper language code). None means automatic detection.
LANGUAGES: dict[str, str | None] = {
    "Auto": None,
    "Spanish": "es",
    "German": "de",
    "French": "fr",
    "Italian": "it",
    "Portuguese": "pt",
    "Dutch": "nl",
    "Polish": "pl",
    "Czech": "cs",
    "Swedish": "sv",
    "Turkish": "tr",
    "Russian": "ru",
    "Ukrainian": "uk",
    "Arabic": "ar",
    "Japanese": "ja",
    "Korean": "ko",
    "Chinese": "zh",
}

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_TRANSCRIPT_DIR = REPOSITORY_ROOT / "var" / "transcripts"
SETTINGS_PATH = REPOSITORY_ROOT / "var" / "run" / "overlay-settings.json"


def load_settings(path: Path = SETTINGS_PATH) -> tuple[str, Path]:
    """Return the remembered language choice and transcript folder (best effort)."""
    language = "Auto"
    directory = DEFAULT_TRANSCRIPT_DIR
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            if data.get("language") in LANGUAGES:
                language = str(data["language"])
            if isinstance(data.get("transcriptDir"), str) and data["transcriptDir"]:
                directory = Path(data["transcriptDir"])
    except (OSError, ValueError):
        pass
    return language, directory


def save_settings(language: str, directory: Path, path: Path = SETTINGS_PATH) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"language": language, "transcriptDir": str(directory)}),
            encoding="utf-8",
        )
    except OSError:
        pass
