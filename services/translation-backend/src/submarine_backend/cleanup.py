import difflib
import re
from collections import deque
from collections.abc import Sequence

import httpx

# Answer the model gives when a segment consists only of non-conversation text.
EMPTY_MARKER = "[NONE]"
# Whole-segment removal is only trusted for short segments (typical ASR boilerplate).
_MAX_REMOVABLE_WORDS = 12


class OllamaCleaner:
    """Optional local-only cleanup of final English subtitles with bounded context."""

    def __init__(
        self,
        *,
        enabled: bool,
        url: str,
        model: str,
        timeout_seconds: float,
        glossary: Sequence[str] = (),
    ) -> None:
        self.enabled = enabled
        self.url = url
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.glossary = tuple(glossary)
        self._context: deque[str] = deque(maxlen=2)

    def build_prompt(self, text: str, source_language: str | None = None) -> str:
        source_code = source_language or "auto"
        source_name = _LANGUAGE_NAMES.get(source_code, "the detected source language")
        glossary_rule = (
            "- Spell these names and terms exactly as written here whenever they "
            f"(or a misheard variant) occur: {', '.join(self.glossary)}.\n"
            if self.glossary
            else ""
        )
        return (
            "You are a careful copy editor for live English subtitles. The text below "
            f"was produced by speech recognition that translated casual {source_name} "
            f"({source_code}) speech into English. Background television or music may "
            "have leaked into it.\n"
            "Rules:\n"
            "- Correct spelling, capitalization, punctuation and obvious grammar slips.\n"
            f"{glossary_rule}"
            "- Keep all other proper names unchanged. Do not infer relationships or "
            "missing context.\n"
            "- Delete typical recognition artifacts that are not part of the "
            "conversation: subtitle or translation credits, 'thanks for watching', "
            "'subscribe' prompts, music or applause tags and immediately repeated "
            "fragments.\n"
            "- Do not add, summarize, explain or rephrase beyond these corrections.\n"
            f"- If nothing of the conversation remains, answer exactly {EMPTY_MARKER}.\n"
            "Produce only the corrected English text, without any additional "
            f"explanations or commentary.\n\n\n{text}"
        )

    def build_translation_prompt(self, text: str, source_language: str | None = None) -> str:
        source_code = source_language or "auto"
        source_name = _LANGUAGE_NAMES.get(source_code, "the detected source language")
        glossary_rule = (
            f"Spell these names exactly like this: {', '.join(self.glossary)}. "
            if self.glossary
            else ""
        )
        return (
            f"You are a professional {source_name} ({source_code}) to English (en) "
            "translator. Your goal is to accurately convey the meaning and nuances "
            f"of the original {source_name} text while adhering to English grammar, "
            "vocabulary, and cultural sensitivities. The text is casual speech from "
            "automatic speech recognition; translate it faithfully and do not add, "
            f"explain or complete anything. {glossary_rule}\n"
            "Produce only the English translation, without any additional explanations "
            f"or commentary. Please translate the following {source_name} text into "
            f"English:\n\n\n{text}"
        )

    async def translate(self, text: str, source_language: str | None = None) -> str | None:
        """Translate source-language text to English; None means "use the fallback"."""
        if not self.enabled:
            return None
        answer = await self._chat(self.build_translation_prompt(text, source_language))
        if answer is None:
            return None
        answer = answer.strip()
        if not answer or len(answer) > len(text) * 3 + 40:
            return None
        return answer

    def accept(self, text: str, cleaned: str) -> str:
        """Validate the model answer; fall back to the raw text when in doubt."""
        cleaned = cleaned.strip()
        if not cleaned:
            return text
        if cleaned.strip(" .\"'") == EMPTY_MARKER:
            return "" if len(text.split()) <= _MAX_REMOVABLE_WORDS else text
        if EMPTY_MARKER in cleaned or len(cleaned) > len(text) * 2 + 40:
            return text
        for name in _proper_names(text):
            if name.casefold() in cleaned.casefold():
                continue
            # A name may only disappear when it was corrected to a glossary term.
            if not difflib.get_close_matches(name, self.glossary, n=1, cutoff=0.7):
                return text
        return cleaned

    async def clean(self, text: str, source_language: str | None = None) -> str:
        if not self.enabled:
            return text
        cleaned = await self._chat(self.build_prompt(text, source_language))
        if cleaned is None:
            return text
        result = self.accept(text, cleaned)
        if result and result is not text:
            self._context.append(result)
        return result

    async def _chat(self, prompt: str) -> str | None:
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
                return str(payload.get("message", {}).get("content", ""))
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
            return None


def _proper_names(text: str) -> list[str]:
    return re.findall(r"(?<!^)\b[A-ZÀ-ÖØ-Þ][\wÀ-ÿ'-]+\b", text)


_LANGUAGE_NAMES = {
    "es": "Spanish",
    "de": "German",
    "fr": "French",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "pl": "Polish",
    "cs": "Czech",
    "sv": "Swedish",
    "tr": "Turkish",
    "uk": "Ukrainian",
    "ar": "Arabic",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
    "ru": "Russian",
    "en": "English",
}
