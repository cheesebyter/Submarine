from typing import Literal

import pytest

from submarine_backend.cleanup import OllamaCleaner
from submarine_backend.translation import (
    ModelStatus,
    SpeechSegmenter,
    TranslationEngine,
    TranslationResult,
    TranslationSession,
    sanitize_transcript,
)


def _frame(amplitude: int = 0) -> bytes:
    return int(amplitude).to_bytes(2, "little", signed=True) * 320


def test_silence_never_emits_a_segment() -> None:
    segmenter = SpeechSegmenter()
    events = [event for _ in range(200) for event in segmenter.feed(_frame())]
    assert events == []
    assert segmenter.flush() is None


def test_speech_is_finalized_after_600ms_silence() -> None:
    segmenter = SpeechSegmenter()
    events = [
        event for frame in [_frame(4000)] * 20 + [_frame()] * 30 for event in segmenter.feed(frame)
    ]
    assert [event.kind for event in events] == ["final"]


def test_long_speech_emits_provisional_output() -> None:
    segmenter = SpeechSegmenter()
    events = [event for _ in range(60) for event in segmenter.feed(_frame(4000))]
    assert "provisional" in [event.kind for event in events]


def test_repeated_multiword_hallucination_collapses_to_one_phrase() -> None:
    phrase = "I will call you first Mira"
    text = " ".join([phrase] * 12)

    assert sanitize_transcript(text, audio_seconds=3) == phrase


def test_single_word_emphasis_and_normal_sentence_are_preserved() -> None:
    text = "No no, I really really do not want to go."
    assert sanitize_transcript(text, audio_seconds=4) == text


def test_implausibly_long_non_repeating_output_is_bounded() -> None:
    text = " ".join(f"word{number}" for number in range(100))
    result = sanitize_transcript(text, audio_seconds=1)
    assert len(result.split()) == 13


class StubEngine(TranslationEngine):
    @property
    def status(self) -> ModelStatus:
        return ModelStatus.READY

    async def load(self) -> None:
        return

    def translate(self, pcm_s16le: bytes) -> TranslationResult:
        return TranslationResult("Hello.", "es", 0.99, 1.0)


async def _ignore_result(
    kind: Literal["provisional", "final"],
    sequence: int,
    result: TranslationResult,
) -> None:
    return


async def _ignore_error(error: str) -> None:
    return


def test_translation_queue_drops_oldest_frame_at_capacity() -> None:
    session = TranslationSession(
        StubEngine(),
        _ignore_result,
        _ignore_error,
        queue_capacity=2,
    )
    session.push(_frame(1000))
    session.push(_frame(2000))
    session.push(_frame(3000))
    assert session.dropped_frames == 1


@pytest.mark.asyncio
async def test_translation_session_emits_final_result() -> None:
    results: list[tuple[str, int, str]] = []

    async def result_callback(
        kind: Literal["provisional", "final"],
        sequence: int,
        result: TranslationResult,
    ) -> None:
        results.append((kind, sequence, result.text))

    async def error_callback(error: str) -> None:
        raise AssertionError(error)

    session = TranslationSession(StubEngine(), result_callback, error_callback)
    session.start()
    for _ in range(20):
        session.push(_frame(4000))
    await session.finish()

    assert results[-1] == ("final", 0, "Hello.")


@pytest.mark.asyncio
async def test_cleanup_runs_only_for_final_results() -> None:
    class TrackingCleaner(OllamaCleaner):
        def __init__(self) -> None:
            super().__init__(
                enabled=True,
                url="http://127.0.0.1:11434",
                model="test",
                timeout_seconds=1,
            )
            self.inputs: list[str] = []

        async def clean(self, text: str, source_language: str | None = None) -> str:
            self.inputs.append(text)
            return "Clean English."

    cleaner = TrackingCleaner()
    results: list[tuple[str, str]] = []

    async def result_callback(
        kind: Literal["provisional", "final"],
        sequence: int,
        result: TranslationResult,
    ) -> None:
        results.append((kind, result.text))

    session = TranslationSession(
        StubEngine(),
        result_callback,
        _ignore_error,
        cleaner=cleaner,
    )
    session.start()
    for _ in range(60):
        session.push(_frame(4000))
    await session.finish()

    assert any(kind == "provisional" for kind, _ in results)
    assert cleaner.inputs == ["Hello."]
    assert results[-1] == ("final", "Clean English.")
