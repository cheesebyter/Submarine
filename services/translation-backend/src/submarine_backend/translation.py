import asyncio
import contextlib
import gc
import logging
import math
import os
import re
import time
from abc import ABC, abstractmethod
from collections import deque
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

import numpy as np

from submarine_backend.cleanup import OllamaCleaner

_DLL_DIRECTORY_HANDLES: list[Any] = []
# Child of uvicorn's logger so the lines appear in the backend console.
# Only confidence numbers are logged, never transcript text.
_LOGGER = logging.getLogger("uvicorn.error.submarine")


class ModelStatus(StrEnum):
    LOADING = "loading"
    READY = "ready"
    MODEL_MISSING = "model_missing"
    CUDA_UNAVAILABLE = "cuda_unavailable"
    LOAD_FAILED = "load_failed"


@dataclass(frozen=True, slots=True)
class TranslationResult:
    text: str
    source_language: str | None
    language_probability: float
    inference_ms: float
    original_text: str | None = None


_MAX_ORIGINAL_CHARS = 1500
# Stock phrases Whisper emits for music or noise. A segment is dropped only when
# it consists of exactly one of them.
_STOCK_HALLUCINATIONS = frozenset(
    {
        "gracias por ver el video",
        "gracias por ver",
        "muchas gracias por ver el video",
        "suscribete",
        "suscribete al canal",
        "subtitulos realizados por la comunidad de amara org",
        "subtitulos por la comunidad de amara org",
        "thank you for watching",
        "thanks for watching",
        "thank you very much for watching",
        "the end",
        "subtitles by the amara org community",
        "please subscribe",
    }
)


def is_stock_hallucination(text: str) -> bool:
    key = _stock_key(text)
    return not key or key in _STOCK_HALLUCINATIONS


def _stock_key(text: str) -> str:
    import unicodedata

    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", plain.casefold()).strip()


@dataclass(frozen=True, slots=True)
class WhisperOptions:
    """Decoding and VAD settings shared by the translate and transcribe passes."""

    default_language: str | None = None
    initial_prompt: str = ""
    translation_prompt: str = ""
    no_speech_threshold: float = 0.6
    log_prob_threshold: float = -1.0
    vad_threshold: float = 0.5
    vad_min_silence_ms: int = 500
    vad_min_speech_ms: int = 0
    vad_speech_pad_ms: int = 400

    def transcribe_kwargs(self, task: Literal["translate", "transcribe"]) -> dict[str, Any]:
        prompt = self.translation_prompt if task == "translate" else self.initial_prompt
        return {
            "task": task,
            "beam_size": 1,
            "temperature": 0.0,
            # Never feed earlier output back in: one hallucinated segment would
            # otherwise become context for the following ones.
            "condition_on_previous_text": False,
            "initial_prompt": prompt or None,
            "no_speech_threshold": self.no_speech_threshold,
            "log_prob_threshold": self.log_prob_threshold,
            "vad_filter": True,
            "vad_parameters": {
                "threshold": self.vad_threshold,
                "min_silence_duration_ms": self.vad_min_silence_ms,
                "min_speech_duration_ms": self.vad_min_speech_ms,
                "speech_pad_ms": self.vad_speech_pad_ms,
            },
        }

    def join_confident_segments(
        self,
        segments: Any,
        prompt: str,
        *,
        strict: bool = True,
    ) -> str:
        """Drop segments whose average log-probability is below the threshold.

        faster-whisper itself skips a segment only when the no-speech probability
        is high *and* the log-probability is low. With a single temperature a low
        log-probability alone never triggers a retry, so it is filtered here. The
        no-speech probability alone is not used: it is routinely high for real
        speech over background music and would discard almost everything.

        ``strict=False`` (direct Whisper translation) keeps every segment: its
        log-probabilities are generally lower and do not separate real from
        invented text.
        """
        kept: list[str] = []
        dropped = 0
        for segment in segments:
            text = str(segment.text).strip()
            if not text:
                continue
            if is_stock_hallucination(text):
                dropped += 1
                _LOGGER.info("segment dropped: stock phrase or punctuation only")
                continue
            log_prob = float(getattr(segment, "avg_logprob", 0.0))
            if strict and log_prob < self.log_prob_threshold:
                dropped += 1
                _LOGGER.info(
                    "segment dropped: avg_logprob=%.2f no_speech_prob=%.2f",
                    log_prob,
                    float(getattr(segment, "no_speech_prob", 0.0)),
                )
                continue
            kept.append(text)
        joined = " ".join(kept).strip()
        if joined and _echoes_prompt(joined, prompt):
            _LOGGER.info("segment dropped: prompt echo")
            return ""
        if not kept and not dropped:
            _LOGGER.debug("no speech found by VAD/decoder")
        return joined


def _echoes_prompt(text: str, prompt: str) -> bool:
    """On near-silence Whisper tends to repeat (parts of) its own prompt."""
    normalized = " ".join(_normalize_token(token) for token in text.split()).strip()
    if not normalized or not prompt:
        return False
    normalized_prompt = " ".join(_normalize_token(token) for token in prompt.split())
    return len(normalized.split()) >= 2 and normalized in normalized_prompt


def sanitize_transcript(text: str, audio_seconds: float) -> str:
    """Collapse exact phrase loops and cap implausible ASR output."""
    tokens = text.split()
    output: list[str] = []
    index = 0
    while index < len(tokens):
        repeated = False
        maximum_phrase = min(20, (len(tokens) - index) // 2)
        for phrase_length in range(2, maximum_phrase + 1):
            phrase = tokens[index : index + phrase_length]
            normalized = [_normalize_token(token) for token in phrase]
            following = tokens[index + phrase_length : index + (2 * phrase_length)]
            if normalized != [_normalize_token(token) for token in following]:
                continue
            output.extend(phrase)
            index += 2 * phrase_length
            while index + phrase_length <= len(tokens) and normalized == [
                _normalize_token(token) for token in tokens[index : index + phrase_length]
            ]:
                index += phrase_length
            repeated = True
            break
        if not repeated:
            output.append(tokens[index])
            index += 1

    # Speech rarely exceeds five English tokens per second. The extra allowance
    # prevents clipping very short, fast phrases while bounding hallucinations.
    maximum_tokens = max(12, round(audio_seconds * 5) + 8)
    return " ".join(output[:maximum_tokens]).strip()


def _normalize_token(token: str) -> str:
    return re.sub(r"^\W+|\W+$", "", token, flags=re.UNICODE).casefold()


class TranslationEngine(ABC):
    @property
    @abstractmethod
    def status(self) -> ModelStatus:
        raise NotImplementedError

    @property
    def ready(self) -> bool:
        return self.status == ModelStatus.READY

    @abstractmethod
    async def load(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def translate(self, pcm_s16le: bytes) -> TranslationResult:
        raise NotImplementedError

    async def translate_async(self, pcm_s16le: bytes) -> TranslationResult:
        return await asyncio.to_thread(self.translate, pcm_s16le)

    async def close(self) -> None:
        return

    def set_source_language(self, language: str | None) -> None:
        return

    def transcribe_original(self, pcm_s16le: bytes, language: str | None) -> str:
        """Return the untranslated transcript; engines without support return nothing."""
        return ""

    async def transcribe_original_async(self, pcm_s16le: bytes, language: str | None) -> str:
        return await asyncio.to_thread(self.transcribe_original, pcm_s16le, language)


class FasterWhisperTranslationEngine(TranslationEngine):
    def __init__(
        self,
        model_path: Path,
        *,
        device: str = "cuda",
        compute_type: str = "float16",
        options: WhisperOptions | None = None,
    ) -> None:
        self.model_path = model_path
        self.device = device
        self.compute_type = compute_type
        self.options = options or WhisperOptions()
        self._status = ModelStatus.MODEL_MISSING
        self._model: Any = None
        self.diagnostic: str | None = None
        self.source_language: str | None = self.options.default_language
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="submarine-gpu")

    @property
    def status(self) -> ModelStatus:
        return self._status

    async def load(self) -> None:
        if not (self.model_path / "model.bin").is_file():
            self._status = ModelStatus.MODEL_MISSING
            self.diagnostic = "Run scripts/download-whisper-model.ps1."
            return

        self._status = ModelStatus.LOADING
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(self._executor, self._load_blocking)
        except Exception as error:
            message = str(error).lower()
            self._status = (
                ModelStatus.CUDA_UNAVAILABLE
                if any(term in message for term in ("cublas", "cudnn", "cuda"))
                else ModelStatus.LOAD_FAILED
            )
            self.diagnostic = type(error).__name__
            return
        self._status = ModelStatus.READY
        self.diagnostic = None

    def _load_blocking(self) -> None:
        _configure_nvidia_dll_directories()
        from faster_whisper import WhisperModel  # type: ignore[import-untyped]

        self._model = WhisperModel(
            str(self.model_path),
            device=self.device,
            compute_type=self.compute_type,
            local_files_only=True,
        )
        warmup_segments, _ = self._model.transcribe(
            np.zeros(16000, dtype=np.float32),
            language="en",
            beam_size=1,
            vad_filter=False,
        )
        list(warmup_segments)

    def translate(self, pcm_s16le: bytes) -> TranslationResult:
        if not self.ready or self._model is None:
            raise RuntimeError(f"Translation model is not ready: {self.status}")

        audio = np.frombuffer(pcm_s16le, dtype="<i2").astype(np.float32)
        audio /= 32768.0
        started = time.perf_counter()
        segments, info = self._model.transcribe(
            audio,
            language=self.source_language,
            **self.options.transcribe_kwargs("translate"),
        )
        text = self.options.join_confident_segments(
            segments, self.options.translation_prompt, strict=False
        )
        return TranslationResult(
            text=text,
            source_language=getattr(info, "language", None),
            language_probability=float(getattr(info, "language_probability", 0.0)),
            inference_ms=(time.perf_counter() - started) * 1000,
        )

    def transcribe_original(self, pcm_s16le: bytes, language: str | None) -> str:
        if not self.ready or self._model is None:
            raise RuntimeError(f"Translation model is not ready: {self.status}")

        audio = np.frombuffer(pcm_s16le, dtype="<i2").astype(np.float32)
        audio /= 32768.0
        segments, _ = self._model.transcribe(
            audio,
            language=self.source_language or language,
            **self.options.transcribe_kwargs("transcribe"),
        )
        return self.options.join_confident_segments(segments, self.options.initial_prompt)

    async def translate_async(self, pcm_s16le: bytes) -> TranslationResult:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, self.translate, pcm_s16le)

    async def transcribe_original_async(self, pcm_s16le: bytes, language: str | None) -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._executor, self.transcribe_original, pcm_s16le, language
        )

    async def close(self) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(self._executor, self._close_blocking)
        self._executor.shutdown(wait=True)

    def _close_blocking(self) -> None:
        self._model = None
        gc.collect()
        while _DLL_DIRECTORY_HANDLES:
            _DLL_DIRECTORY_HANDLES.pop().close()
        if self._status == ModelStatus.READY:
            self._status = ModelStatus.MODEL_MISSING

    def set_source_language(self, language: str | None) -> None:
        # "Auto" from a client means "no override": fall back to the configured
        # default, which is automatic detection unless SUBMARINE_SOURCE_LANGUAGE is set.
        self.source_language = language or self.options.default_language


def _configure_nvidia_dll_directories() -> None:
    if os.name != "nt":
        return
    import nvidia.cublas  # type: ignore[import-untyped]
    import nvidia.cudnn  # type: ignore[import-untyped]

    for package in (nvidia.cublas, nvidia.cudnn):
        package_directory = Path(next(iter(package.__path__)))
        binary_directory = package_directory / "bin"
        if binary_directory.is_dir():
            _DLL_DIRECTORY_HANDLES.append(os.add_dll_directory(str(binary_directory)))


@dataclass(frozen=True, slots=True)
class SegmentEvent:
    kind: Literal["provisional", "final"]
    audio: bytes


class SpeechSegmenter:
    """Energy gate for live chunking; faster-whisper applies Silero VAD again."""

    def __init__(
        self,
        *,
        speech_rms_threshold: float = 0.008,
        silence_frames_to_finalize: int = 30,
        provisional_interval_frames: int = 50,
        minimum_speech_frames: int = 15,
        maximum_segment_frames: int = 600,
        preroll_frames: int = 10,
    ) -> None:
        self.speech_rms_threshold = speech_rms_threshold
        self.silence_frames_to_finalize = silence_frames_to_finalize
        self.provisional_interval_frames = provisional_interval_frames
        self.minimum_speech_frames = minimum_speech_frames
        self.maximum_segment_frames = maximum_segment_frames
        self._preroll: deque[bytes] = deque(maxlen=preroll_frames)
        self._active: list[bytes] = []
        self._speech_frames = 0
        self._silence_frames = 0
        self._last_provisional_at = 0

    def feed(self, frame: bytes) -> list[SegmentEvent]:
        is_speech = pcm_rms(frame) >= self.speech_rms_threshold
        if not self._active:
            self._preroll.append(frame)
            if not is_speech:
                return []
            self._active = list(self._preroll)
            self._preroll.clear()
        else:
            self._active.append(frame)
        if is_speech:
            self._speech_frames += 1
            self._silence_frames = 0
        else:
            self._silence_frames += 1

        events: list[SegmentEvent] = []
        active_count = len(self._active)
        if (
            is_speech
            and self._speech_frames >= self.minimum_speech_frames
            and active_count - self._last_provisional_at >= self.provisional_interval_frames
        ):
            events.append(SegmentEvent("provisional", b"".join(self._active)))
            self._last_provisional_at = active_count

        if (
            self._silence_frames >= self.silence_frames_to_finalize
            or active_count >= self.maximum_segment_frames
        ):
            final = self._finish()
            if final is not None:
                events.append(final)
        return events

    def flush(self) -> SegmentEvent | None:
        return self._finish()

    def reset(self) -> None:
        self._preroll.clear()
        self._active.clear()
        self._speech_frames = 0
        self._silence_frames = 0
        self._last_provisional_at = 0

    def _finish(self) -> SegmentEvent | None:
        audio = b"".join(self._active)
        enough_speech = self._speech_frames >= self.minimum_speech_frames
        self.reset()
        return SegmentEvent("final", audio) if enough_speech else None


def pcm_rms(frame: bytes) -> float:
    samples = np.frombuffer(frame, dtype="<i2").astype(np.float32)
    if samples.size == 0:
        return 0.0
    samples /= 32768.0
    return math.sqrt(float(np.mean(np.square(samples))))


ResultCallback = Callable[
    [Literal["provisional", "final"], int, TranslationResult],
    Awaitable[None],
]
ErrorCallback = Callable[[str], Awaitable[None]]


class TranslationSession:
    def __init__(
        self,
        engine: TranslationEngine,
        on_result: ResultCallback,
        on_error: ErrorCallback,
        *,
        queue_capacity: int = 500,
        cleaner: OllamaCleaner | None = None,
        speech_rms_threshold: float = 0.008,
        translate_finals_with_cleaner: bool = False,
    ) -> None:
        self.engine = engine
        self.on_result = on_result
        self.on_error = on_error
        self.queue_capacity = queue_capacity
        self.cleaner = cleaner
        self.include_original = False
        self.translate_finals_with_cleaner = translate_finals_with_cleaner
        self.dropped_frames = 0
        self._queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=queue_capacity)
        self._segmenter = SpeechSegmenter(speech_rms_threshold=speech_rms_threshold)
        self._sequence = 0
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task is not None:
            raise RuntimeError("Translation session is already running")
        self._task = asyncio.create_task(self._run())

    def push(self, frame: bytes) -> None:
        if self._queue.full():
            with contextlib.suppress(asyncio.QueueEmpty):
                self._queue.get_nowait()
                self._queue.task_done()
                self.dropped_frames += 1
        self._queue.put_nowait(frame)

    def set_source_language(self, language: str | None) -> None:
        self.engine.set_source_language(language)

    def configure(self, language: str | None, include_original: bool | None = None) -> None:
        self.engine.set_source_language(language)
        if include_original is not None:
            self.include_original = include_original

    async def finish(self) -> None:
        if self._task is None:
            return
        if self._queue.full():
            with contextlib.suppress(asyncio.QueueEmpty):
                self._queue.get_nowait()
                self._queue.task_done()
        self._queue.put_nowait(None)
        await self._task
        self._task = None

    async def cancel(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._segmenter.reset()
        self._task = None

    async def _run(self) -> None:
        while True:
            frame = await self._queue.get()
            try:
                if frame is None:
                    final = self._segmenter.flush()
                    if final is not None:
                        await self._translate(final)
                    return
                for event in self._segmenter.feed(frame):
                    await self._translate(event)
            finally:
                self._queue.task_done()

    async def _translate(self, event: SegmentEvent) -> None:
        if (
            event.kind == "final"
            and self.translate_finals_with_cleaner
            and self.cleaner is not None
            and self.cleaner.enabled
            and await self._transcribe_then_translate(event)
        ):
            self._sequence += 1
            return
        try:
            result = await self.engine.translate_async(event.audio)
        except Exception as error:
            await self.on_error(type(error).__name__)
            return
        audio_seconds = len(event.audio) / (16000 * 2)
        result = replace(result, text=sanitize_transcript(result.text, audio_seconds))
        if result.text:
            if event.kind == "final":
                result = await self._finalize(result, event.audio, audio_seconds)
            await self.on_result(event.kind, self._sequence, result)
        if event.kind == "final":
            self._sequence += 1

    async def _finalize(
        self,
        result: TranslationResult,
        audio: bytes,
        audio_seconds: float,
    ) -> TranslationResult:
        if self.include_original:
            try:
                original = await self.engine.transcribe_original_async(
                    audio, result.source_language
                )
            except Exception as error:
                await self.on_error(type(error).__name__)
            else:
                original = sanitize_transcript(original, audio_seconds)
                result = replace(result, original_text=original[:_MAX_ORIGINAL_CHARS] or None)
        if self.cleaner is not None:
            cleaned = await self.cleaner.clean(result.text, result.source_language)
            result = replace(result, text=sanitize_transcript(cleaned, audio_seconds))
        return result

    async def _transcribe_then_translate(self, event: SegmentEvent) -> bool:
        """Final path of the "ollama" mode. Returns False to use the Whisper fallback."""
        assert self.cleaner is not None
        audio_seconds = len(event.audio) / (16000 * 2)
        started = time.perf_counter()
        try:
            original = await self.engine.transcribe_original_async(event.audio, None)
        except Exception as error:
            await self.on_error(type(error).__name__)
            return False
        original = sanitize_transcript(original, audio_seconds)[:_MAX_ORIGINAL_CHARS]
        language = getattr(self.engine, "source_language", None)
        text = ""
        if original:
            translated = await self.cleaner.translate(original, language)
            if translated is None:
                return False
            text = sanitize_transcript(translated, audio_seconds)
        # An empty final (no speech in the source language) still clears the
        # provisional line in the overlay.
        await self.on_result(
            "final",
            self._sequence,
            TranslationResult(
                text=text,
                source_language=language,
                language_probability=1.0 if language else 0.0,
                inference_ms=(time.perf_counter() - started) * 1000,
                original_text=(original or None) if self.include_original else None,
            ),
        )
        return True
