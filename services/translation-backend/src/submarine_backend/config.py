from functools import lru_cache
from ipaddress import ip_address
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPOSITORY_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    """Validated process configuration with local-only defaults."""

    model_config = SettingsConfigDict(
        # The ignored repository-root .env is the documented location; a .env in
        # the working directory (services/translation-backend) overrides it.
        env_file=(_REPOSITORY_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        env_prefix="SUBMARINE_",
        extra="ignore",
    )

    app_name: str = "Submarine Translation Backend"
    host: str = "127.0.0.1"
    port: int = Field(default=8765, ge=1024, le=65535)
    log_level: str = "info"
    model_path: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[4]
        / "var/models/faster-whisper-large-v3"
    )
    model_name: str = "Systran/faster-whisper-large-v3"
    model_device: str = "cuda"
    model_compute_type: str = "float16"
    # Whisper decoding. An unset source language keeps automatic detection.
    source_language: str | None = Field(default=None, pattern=r"^[a-z]{2,3}$")
    # Prompt in the *spoken* language; biases the original-language transcript.
    initial_prompt: str = Field(default="", max_length=600)
    # Prompt in *English*; biases names and terms of the English translation.
    translation_prompt: str = Field(default="", max_length=600)
    no_speech_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    log_prob_threshold: float = Field(default=-1.0, ge=-5.0, le=0.0)
    vad_threshold: float = Field(default=0.5, ge=0.1, le=0.95)
    vad_min_silence_ms: int = Field(default=500, ge=100, le=5000)
    vad_min_speech_ms: int = Field(default=0, ge=0, le=2000)
    vad_speech_pad_ms: int = Field(default=400, ge=0, le=1000)
    # Energy gate in front of Whisper (RMS of 20 ms frames, 0..1).
    speech_rms_threshold: float = Field(default=0.008, ge=0.001, le=0.5)
    # Comma-separated names and terms the cleanup must spell exactly like this.
    glossary: str = Field(default="", max_length=600)
    # "whisper": Whisper translates directly (default). "ollama": final segments
    # are transcribed in the source language and translated by the local Ollama
    # model; needs ollama_cleanup_enabled and falls back to "whisper" on errors.
    translation_mode: Literal["whisper", "ollama"] = "whisper"
    ollama_cleanup_enabled: bool = False
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:14b"
    ollama_timeout_seconds: float = Field(default=15.0, ge=1.0, le=60.0)

    @field_validator("source_language", mode="before")
    @classmethod
    def empty_source_language_is_auto(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip().lower()
            return value or None
        return value

    @property
    def glossary_terms(self) -> tuple[str, ...]:
        return tuple(term.strip() for term in self.glossary.split(",") if term.strip())

    @field_validator("ollama_url")
    @classmethod
    def require_loopback_ollama(cls, value: str) -> str:
        from urllib.parse import urlparse

        parsed = urlparse(value)
        if parsed.scheme != "http" or parsed.hostname is None:
            raise ValueError("ollama_url must be an HTTP loopback URL")
        try:
            is_loopback = ip_address(parsed.hostname).is_loopback
        except ValueError as error:
            raise ValueError("ollama_url must use a loopback IP address") from error
        if not is_loopback:
            raise ValueError("ollama_url must use a loopback IP address")
        return value.rstrip("/")

    @field_validator("host")
    @classmethod
    def require_loopback_host(cls, value: str) -> str:
        try:
            is_loopback = ip_address(value).is_loopback
        except ValueError as error:
            raise ValueError("host must be a loopback IP address") from error
        if not is_loopback:
            raise ValueError("host must be a loopback IP address")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
