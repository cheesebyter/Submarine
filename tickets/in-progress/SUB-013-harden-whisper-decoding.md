# SUB-013: Harden Whisper decoding against background audio

- Status: In progress
- Priority: P1
- Owner: Unassigned
- Depends on: SUB-004, SUB-006, SUB-012

## Objective

Reduce hallucinations, missing punctuation and misspelled names for speech with
television or music in the background by making decoding, VAD, prompts and the
optional Ollama cleanup configurable and stricter.

## Scope

- `SUBMARINE_SOURCE_LANGUAGE` as backend default; overlay "Auto" falls back to it.
- Configurable `no_speech_threshold`, `log_prob_threshold`, Silero VAD parameters
  and the energy gate; segments below the log-probability limit are dropped (logged without text).
- Per-task prompts (`SUBMARINE_INITIAL_PROMPT` for the original transcript,
  `SUBMARINE_TRANSLATION_PROMPT` for the English translation) with a guard
  against prompt echo.
- Ollama cleanup prompt rewritten as copy-editing with a glossary; a short
  artifact-only segment may be removed entirely.
- `SUBMARINE_TRANSLATION_MODE=ollama`: final segments are transcribed in the
  source language and translated by Ollama, with fallback to Whisper translation.
- Exact-match filter for stock hallucination phrases.
- Settings are read from the repository-root `.env` (UTF-8) as documented.

## Non-goals

- Speaker separation or removing intelligible television speech reliably.
- Changing the capture path or protocol.

## Acceptance criteria

- [x] Language, thresholds, VAD and prompts are configurable and validated.
- [x] Uncertain segments and prompt echoes are discarded.
- [x] Cleanup keeps falling back to the raw text on any doubt.
- [x] Tests do not depend on a local `.env`.
- [ ] Manual verification with the real recording on the GPU machine.

## Verification

- Automated: 65 backend tests pass (new: options, segment filter, language
  fallback, cleanup acceptance rules, settings normalization); ruff lint clean.
- Measured (CPU int8, large-v3, samples of the 37-minute test recording):
  direct Whisper translation invented or distorted content on most sampled
  segments regardless of prompt and beam size; the Spanish transcript was closer.
  `no_speech_prob` and translate log-probabilities did not separate real from
  invented text. Prompts caused invented text on speech-free segments.
- Manual: Pending — GPU run with Ollama on the Windows machine.
- Evidence: Pending manual run.

## Related

- SUB-006, SUB-009, SUB-012
