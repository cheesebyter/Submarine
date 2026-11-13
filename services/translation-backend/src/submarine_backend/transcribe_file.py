"""Offline transcription of one audio or video file into plain-text files.

Explicit, user-started tool (SUB-012 retention rules apply to its output):
writes ``<name>_original.txt`` next to the input and, with ``--translate``,
``<name>_english.txt`` through the local Ollama model.
"""

import argparse
import asyncio
import time
from pathlib import Path
from typing import Any

import numpy as np

from submarine_backend.cleanup import OllamaCleaner
from submarine_backend.config import Settings, get_settings
from submarine_backend.translation import (
    WhisperOptions,
    _configure_nvidia_dll_directories,
    _stock_key,
    is_stock_hallucination,
)


def _load_audio(path: Path) -> np.ndarray[Any, np.dtype[np.float32]]:
    # Own decoder: faster-whisper's decode_audio is incompatible with the pinned PyAV.
    import av
    from av.audio.resampler import AudioResampler

    chunks: list[np.ndarray[Any, Any]] = []
    with av.open(str(path)) as container:
        resampler = AudioResampler(format="s16", layout="mono", rate=16000)
        for frame in container.decode(audio=0):
            chunks.extend(
                converted.to_ndarray().reshape(-1) for converted in resampler.resample(frame)
            )
        chunks.extend(converted.to_ndarray().reshape(-1) for converted in resampler.resample(None))
    if not chunks:
        raise RuntimeError("Die Datei enthält keine Audiospur.")
    return np.concatenate(chunks).astype(np.float32) / 32768.0


def _stamp(seconds: float) -> str:
    total = int(seconds)
    return f"{total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d}"


def _options(settings: Settings) -> WhisperOptions:
    return WhisperOptions(
        initial_prompt=settings.initial_prompt,
        no_speech_threshold=settings.no_speech_threshold,
        log_prob_threshold=settings.log_prob_threshold,
        vad_threshold=settings.vad_threshold,
        vad_min_silence_ms=settings.vad_min_silence_ms,
        vad_min_speech_ms=settings.vad_min_speech_ms,
        vad_speech_pad_ms=settings.vad_speech_pad_ms,
    )


def transcribe(
    path: Path,
    settings: Settings,
    *,
    language: str | None,
    device: str,
    compute_type: str,
) -> list[tuple[float, str]]:
    from faster_whisper import WhisperModel  # type: ignore[import-untyped]

    if not (settings.model_path / "model.bin").is_file():
        raise RuntimeError("Model missing. Run scripts/download-whisper-model.ps1.")
    if device == "cuda":
        _configure_nvidia_dll_directories()
    model = WhisperModel(
        str(settings.model_path.resolve()),
        device=device,
        compute_type=compute_type,
        local_files_only=True,
    )
    options = _options(settings)
    kwargs = options.transcribe_kwargs("transcribe")
    # Offline there is no latency budget: a wider beam is more accurate.
    kwargs["beam_size"] = 5
    audio = _load_audio(path)
    duration = len(audio) / 16000
    segments, info = model.transcribe(audio, language=language, **kwargs)
    print(f"Sprache: {info.language} · Dauer: {_stamp(duration)}", flush=True)

    lines: list[tuple[float, str]] = []
    previous = ""
    last_report = time.monotonic()
    for segment in segments:
        text = " ".join(str(segment.text).split())
        if (
            not text
            or is_stock_hallucination(text)
            or float(segment.avg_logprob) < options.log_prob_threshold
            or _stock_key(text) == previous
        ):
            continue
        previous = _stock_key(text)
        lines.append((float(segment.start), text))
        if time.monotonic() - last_report >= 10:
            print(f"  … {_stamp(segment.end)} / {_stamp(duration)}", flush=True)
            last_report = time.monotonic()
    return lines


async def _translate(
    lines: list[tuple[float, str]],
    settings: Settings,
    language: str | None,
) -> list[tuple[float, str]]:
    cleaner = OllamaCleaner(
        enabled=True,
        url=settings.ollama_url,
        model=settings.ollama_model,
        timeout_seconds=settings.ollama_timeout_seconds,
        glossary=settings.glossary_terms,
    )
    translated: list[tuple[float, str]] = []
    for index, (start, text) in enumerate(lines, 1):
        english = await cleaner.translate(text, language)
        translated.append((start, english or "[Übersetzung fehlgeschlagen]"))
        if index % 25 == 0:
            print(f"  … übersetzt {index}/{len(lines)}", flush=True)
    return translated


def _write(path: Path, lines: list[tuple[float, str]]) -> None:
    path.write_text(
        "".join(f"[{_stamp(start)}] {text}\n" for start, text in lines),
        encoding="utf-8",
        newline="\n",
    )
    print(f"Geschrieben: {path}", flush=True)


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Transcribe one audio/video file locally")
    parser.add_argument("media", type=Path)
    parser.add_argument("--language", default=settings.source_language)
    parser.add_argument("--translate", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--device", default=settings.model_device)
    parser.add_argument("--compute-type", default=settings.model_compute_type)
    arguments = parser.parse_args()
    media: Path = arguments.media
    if not media.is_file():
        raise FileNotFoundError(f"Datei nicht gefunden: {media}")
    output_dir: Path = arguments.output_dir or media.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    lines = transcribe(
        media,
        settings,
        language=arguments.language or None,
        device=arguments.device,
        compute_type=arguments.compute_type,
    )
    _write(output_dir / f"{media.stem}_original.txt", lines)
    if arguments.translate:
        english = asyncio.run(_translate(lines, settings, arguments.language or None))
        _write(output_dir / f"{media.stem}_english.txt", english)


if __name__ == "__main__":
    main()
