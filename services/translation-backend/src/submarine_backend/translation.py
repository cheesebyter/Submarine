import asyncio
import contextlib
import gc
import math
import os
import re
import time
from abc import ABC, abstractmethod
from collections import deque
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

import numpy as np

from submarine_backend.cleanup import OllamaCleaner

_DLL_DIRECTORY_HANDLES: list[Any] = []


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


class FasterWhisperTranslationEngine(TranslationEngine):
    def __init__(
        self,
        model_path: Path,
        *,
        device: str = "cuda",
        compute_type: str = "float16",
    ) -> None:
        self.model_path = model_path
        self.device = device
        self.compute_type = compute_type
        self._status = ModelStatus.MODEL_MISSING
        self._model: Any = None
        self.diagnostic: str | None = None
        self.source_language: str | None = None
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
            task="translate",
            language=self.source_language,
            beam_size=1,
            temperature=0.0,
            condition_on_previous_text=False,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
        )
        text = " ".join(segment.text.strip() for segment in segments).strip()
        return TranslationResult(
            text=text,
            source_language=getattr(info, "language", None),
            language_probability=float(getattr(info, "language_probability", 0.0)),
            inference_ms=(time.perf_counter() - started) * 1000,
        )

    async def translate_async(self, pcm_s16le: bytes) -> TranslationResult:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, self.translate, pcm_s16le)

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
        self.source_language = language


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
    ) -> None:
        self.engine = engine
        self.on_result = on_result
        self.on_error = on_error
        self.queue_capacity = queue_capacity
        self.cleaner = cleaner
        self.dropped_frames = 0
        self._queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=queue_capacity)
        self._segmenter = SpeechSegmenter()
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
        try:
            result = await self.engine.translate_async(event.audio)
        except Exception as error:
            await self.on_error(type(error).__name__)
            return
        audio_seconds = len(event.audio) / (16000 * 2)
        sanitized = sanitize_transcript(result.text, audio_seconds)
        result = TranslationResult(
            text=sanitized,
            source_language=result.source_language,
            language_probability=result.language_probability,
            inference_ms=result.inference_ms,
        )
        if result.text:
            if event.kind == "final" and self.cleaner is not None:
                cleaned = await self.cleaner.clean(
                    result.text,
                    result.source_language,
                )
                cleaned = sanitize_transcript(cleaned, audio_seconds)
                result = TranslationResult(
                    text=cleaned,
                    source_language=result.source_language,
                    language_probability=result.language_probability,
                    inference_ms=result.inference_ms,
                )
            await self.on_result(event.kind, self._sequence, result)
        if event.kind == "final":
            self._sequence += 1
