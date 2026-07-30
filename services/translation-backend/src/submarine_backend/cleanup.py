import re
from collections import deque

import httpx


class OllamaCleaner:
    """Optional local-only final translation enforcement with bounded context."""

    def __init__(
        self,
        *,
        enabled: bool,
        url: str,
        model: str,
        timeout_seconds: float,
    ) -> None:
        self.enabled = enabled
        self.url = url
        self.model = model
        self.timeout_seconds = timeout_seconds
        self._context: deque[str] = deque(maxlen=2)

    async def clean(self, text: str, source_language: str | None = None) -> str:
        if not self.enabled:
            return text
        source_code = source_language or "auto"
        source_name = _LANGUAGE_NAMES.get(source_code, "the detected source language")
        proper_names = re.findall(r"(?<!^)\b[A-ZÀ-ÖØ-Þ][\wÀ-ÿ'-]+\b", text)
        names_instruction = (
            f"The following proper names must appear unchanged: {', '.join(proper_names)}. "
            if proper_names
            else ""
        )
        prompt = (
            f"You are a professional {source_name} ({source_code}) to English (en) "
            "translator. Your goal is to accurately convey the meaning and nuances "
            f"of the original {source_name} text while adhering to English grammar, "
            "vocabulary, and cultural sensitivities. Preserve proper names exactly "
            f"and do not infer relationships or missing context. {names_instruction}\n"
            "Produce only the English translation, without any additional explanations "
            f"or commentary. Please translate the following {source_name} text into "
            f"English:\n\n\n{text}"
        )
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "stream": False,
                        # A small context avoids Ollama reserving its model's very
                        # large default context beside Whisper on the same GPU.
                        "options": {"temperature": 0, "num_ctx": 2048},
                        "keep_alive": "10m",
                    },
                )
                response.raise_for_status()
                payload = response.json()
                cleaned = str(payload.get("message", {}).get("content", "")).strip()
        except (httpx.HTTPError, ValueError, TypeError):
            return text
        if not cleaned or len(cleaned) > max(8192, len(text) * 4):
            return text
        if any(name.casefold() not in cleaned.casefold() for name in proper_names):
            return text
        self._context.append(cleaned)
        return cleaned


_LANGUAGE_NAMES = {
    "es": "Spanish",
    "de": "German",
    "fr": "French",
    "it": "Italian",
    "pt": "Portuguese",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
    "ru": "Russian",
    "en": "English",
}
