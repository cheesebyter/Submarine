# SUB-004: Implement local Whisper translation

- Status: Done
- Priority: P0
- Owner: Codex
- Depends on: SUB-001, SUB-002

## Objective

Translate incoming speech from automatically detected languages into English
using the local RTX 4090.

## Scope

- faster-whisper model loading on CUDA.
- Voice activity detection, bounded buffering and segmentation.
- Provisional and final translation events.
- Model readiness and useful GPU/model errors.
- A repeatable latency and quality fixture.

## Non-goals

- Ollama cleanup and alternative target languages.

## Acceptance criteria

- [x] No audio or transcript leaves the machine.
- [x] Supported non-English speech produces English final text.
- [x] English speech produces English text without unnecessary translation.
- [x] Silence does not generate recurring hallucinated subtitles.
- [x] Queues remain bounded when inference falls behind.
- [x] Latency measurements are recorded on the RTX 4090 system.

## Verification

- Automated: `.\scripts\check.ps1` and
  `.\scripts\benchmark-translation.ps1`
- Manual: Downloaded the explicit local large-v3 model, verified CUDA warm-up,
  queried the live health endpoint and ran German and English GPU fixtures.
- Evidence: 37 Python tests, 5 extension tests and 22 protocol tests pass. German
  was detected as `de` with 0.9902 probability and translated to English; English
  was detected as `en` with 0.9839 probability and remained English. Warm German
  inference median was 612.8 ms for 7.61 s of audio. The live server reports
  `model_status=ready` on `cuda`. Silence, finalization, queue dropping and
  WebSocket transcript delivery have regression coverage. Full measurements are
  recorded in `docs/benchmarks/rtx4090-large-v3.md`.
