from pathlib import Path
from typing import Literal

import pytest

from submarine_backend.cleanup import OllamaCleaner
from submarine_backend.translation import (
    FasterWhisperTranslationEngine,
    ModelStatus,
    SpeechSegmenter,
    TranslationEngine,
    TranslationResult,
    TranslationSession,
    WhisperOptions,
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


class OriginalEngine(StubEngine):
    def __init__(self) -> None:
        self.original_calls: list[str | None] = []

    def transcribe_original(self, pcm_s16le: bytes, language: str | None) -> str:
        self.original_calls.append(language)
        return "Hola."


@pytest.mark.asyncio
@pytest.mark.parametrize("include_original", [False, True])
async def test_original_text_is_only_transcribed_for_finals_when_requested(
    include_original: bool,
) -> None:
    engine = OriginalEngine()
    results: list[tuple[str, str | None]] = []

    async def result_callback(
        kind: Literal["provisional", "final"],
        sequence: int,
        result: TranslationResult,
    ) -> None:
        results.append((kind, result.original_text))

    session = TranslationSession(engine, result_callback, _ignore_error)
    session.configure("es", include_original)
    assert session.include_original is include_original
    session.start()
    for _ in range(20):
        session.push(_frame(4000))
    await session.finish()

    finals = [original for kind, original in results if kind == "final"]
    provisionals = [original for kind, original in results if kind == "provisional"]
    assert all(original is None for original in provisionals)
    if include_original:
        assert finals == ["Hola."]
        assert engine.original_calls == ["es"]
    else:
        assert finals == [None]
        assert engine.original_calls == []


@pytest.mark.asyncio
async def test_original_failure_reports_error_but_keeps_translation() -> None:
    class FailingEngine(StubEngine):
        def transcribe_original(self, pcm_s16le: bytes, language: str | None) -> str:
            raise RuntimeError("boom")

    errors: list[str] = []
    finals: list[TranslationResult] = []

    async def result_callback(
        kind: Literal["provisional", "final"],
        sequence: int,
        result: TranslationResult,
    ) -> None:
        if kind == "final":
            finals.append(result)

    async def error_callback(error: str) -> None:
        errors.append(error)

    session = TranslationSession(FailingEngine(), result_callback, error_callback)
    session.configure(None, True)
    session.start()
    for _ in range(20):
        session.push(_frame(4000))
    await session.finish()

    assert errors == ["RuntimeError"]
    assert [result.text for result in finals] == ["Hello."]
    assert finals[0].original_text is None


class _Segment:
    def __init__(self, text: str, no_speech_prob: float = 0.0, avg_logprob: float = -0.2) -> None:
        self.text = text
        self.no_speech_prob = no_speech_prob
        self.avg_logprob = avg_logprob


def test_whisper_options_harden_decoding_and_pick_prompt_per_task() -> None:
    options = WhisperOptions(
        initial_prompt="Nombres: Tobi.",
        translation_prompt="Names: Tobi.",
        vad_threshold=0.6,
    )
    translate = options.transcribe_kwargs("translate")
    assert translate["condition_on_previous_text"] is False
    assert translate["no_speech_threshold"] == 0.6
    assert translate["log_prob_threshold"] == -1.0
    assert translate["initial_prompt"] == "Names: Tobi."
    assert translate["vad_filter"] is True
    assert translate["vad_parameters"]["threshold"] == 0.6
    assert options.transcribe_kwargs("transcribe")["initial_prompt"] == "Nombres: Tobi."
    assert WhisperOptions().transcribe_kwargs("translate")["initial_prompt"] is None


def test_uncertain_segments_and_prompt_echo_are_dropped() -> None:
    options = WhisperOptions()
    segments = [
        _Segment(" Hello there. "),
        _Segment("over music", no_speech_prob=0.9),
        _Segment("mumble", avg_logprob=-1.7),
        _Segment("How are you?"),
    ]
    assert options.join_confident_segments(segments, "") == "Hello there. over music How are you?"
    stock = [_Segment("¡Gracias por ver el video!"), _Segment("..."), _Segment("Gracias.")]
    assert options.join_confident_segments(stock, "") == "Gracias."
    prompt = "Casual conversation. Names: Tobi, Angelita."
    assert options.join_confident_segments([_Segment("Names: Tobi, Angelita.")], prompt) == ""
    assert options.join_confident_segments([_Segment("Tobi is here.")], prompt) == "Tobi is here."


def test_engine_falls_back_to_configured_language_for_auto() -> None:
    engine = FasterWhisperTranslationEngine(
        Path("missing-model"), options=WhisperOptions(default_language="es")
    )
    assert engine.source_language == "es"
    engine.set_source_language("de")
    assert engine.source_language == "de"
    engine.set_source_language(None)
    assert engine.source_language == "es"


class _Translator(OllamaCleaner):
    def __init__(self, answer: str | None) -> None:
        super().__init__(enabled=True, url="http://127.0.0.1:11434", model="t", timeout_seconds=1)
        self.answer = answer
        self.cleaned = 0

    async def translate(self, text: str, source_language: str | None = None) -> str | None:
        return self.answer

    async def clean(self, text: str, source_language: str | None = None) -> str:
        self.cleaned += 1
        return text


async def _run_ollama_mode(
    engine: TranslationEngine, cleaner: OllamaCleaner
) -> list[tuple[str, str, str | None]]:
    results: list[tuple[str, str, str | None]] = []

    async def result_callback(
        kind: Literal["provisional", "final"],
        sequence: int,
        result: TranslationResult,
    ) -> None:
        results.append((kind, result.text, result.original_text))

    session = TranslationSession(
        engine, result_callback, _ignore_error, cleaner=cleaner, translate_finals_with_cleaner=True
    )
    session.configure("es", True)
    session.start()
    for _ in range(20):
        session.push(_frame(4000))
    await session.finish()
    return [item for item in results if item[0] == "final"]


@pytest.mark.asyncio
async def test_ollama_mode_translates_the_source_transcript() -> None:
    finals = await _run_ollama_mode(OriginalEngine(), _Translator("Hi."))
    assert finals == [("final", "Hi.", "Hola.")]


@pytest.mark.asyncio
async def test_ollama_mode_falls_back_to_whisper_when_ollama_fails() -> None:
    cleaner = _Translator(None)
    finals = await _run_ollama_mode(OriginalEngine(), cleaner)
    assert finals == [("final", "Hello.", "Hola.")]
    assert cleaner.cleaned == 1


@pytest.mark.asyncio
async def test_ollama_mode_emits_empty_final_without_source_speech() -> None:
    finals = await _run_ollama_mode(StubEngine(), _Translator("unused"))
    assert finals == [("final", "", None)]
