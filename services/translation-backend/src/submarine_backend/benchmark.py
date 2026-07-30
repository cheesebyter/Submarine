import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

import av
from av.audio.resampler import AudioResampler

from submarine_backend.config import get_settings
from submarine_backend.translation import FasterWhisperTranslationEngine


def _pcm16(path: Path) -> bytes:
    chunks: list[bytes] = []
    with av.open(str(path)) as container:
        resampler = AudioResampler(format="s16", layout="mono", rate=16000)
        for frame in container.decode(audio=0):
            chunks.extend(
                converted.to_ndarray().tobytes() for converted in resampler.resample(frame)
            )
        chunks.extend(converted.to_ndarray().tobytes() for converted in resampler.resample(None))
    return b"".join(chunks)


async def _run(paths: list[Path]) -> list[dict[str, Any]]:
    settings = get_settings()
    engine = FasterWhisperTranslationEngine(
        settings.model_path.resolve(),
        device=settings.model_device,
        compute_type=settings.model_compute_type,
    )
    await engine.load()
    if not engine.ready:
        raise RuntimeError(f"Translation model is not ready: {engine.status}")
    results: list[dict[str, Any]] = []
    try:
        for path in paths:
            audio = _pcm16(path)
            result = await engine.translate_async(audio)
            results.append(
                {
                    "fixture": path.name,
                    "audio_seconds": round(len(audio) / 2 / 16000, 2),
                    "detected_language": result.source_language,
                    "language_probability": round(result.language_probability, 4),
                    "inference_ms": round(result.inference_ms, 1),
                    "text": result.text,
                }
            )
    finally:
        await engine.close()
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark local Submarine translation")
    parser.add_argument("audio", nargs="+", type=Path)
    arguments = parser.parse_args()
    missing = [path for path in arguments.audio if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing audio fixture: {missing[0]}")
    print(json.dumps(asyncio.run(_run(arguments.audio)), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
