from functools import lru_cache
from ipaddress import ip_address
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated process configuration with local-only defaults."""

    model_config = SettingsConfigDict(
        env_file=".env",
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
    ollama_cleanup_enabled: bool = False
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:14b"
    ollama_timeout_seconds: float = Field(default=15.0, ge=1.0, le=60.0)

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
