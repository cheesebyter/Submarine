# SUB-006: Add optional Ollama sentence cleanup

- Status: Done
- Priority: P1
- Owner: Unassigned
- Depends on: SUB-004

## Objective

Improve finalized English sentence quality locally without delaying provisional
subtitles or making Ollama mandatory.

## Scope

- Configurable local Ollama endpoint and model.
- Constrained prompt with bounded recent context.
- Timeouts, cancellation and graceful fallback.
- Evaluation fixture comparing raw and cleaned sentences.
- Show the incoming PCM audio level and warn after prolonged silence.
- Allow the user to lock a supported source language for unreliable short
  automatic-detection segments.

## Non-goals

- Cloud LLM support and rewriting provisional text.

## Acceptance criteria

- [x] Cleanup is disabled by default until configured.
- [x] Only finalized text is submitted to Ollama.
- [x] Failure or timeout preserves the original Whisper result.
- [x] Cleanup cannot add commentary, summaries or unsupported facts.
- [x] Requests and responses are not content-logged by default.
- [x] Audio presence is visible and prolonged silence has actionable guidance.
- [x] A fixed source language can override per-segment auto detection.

## Verification

- Automated: `.\scripts\check.ps1` passes Python/TypeScript static checks,
  builds and all component tests. A dedicated session test proves cleanup is
  invoked only for final output.
- Manual: `translategemma:4b` uses about 2.9 GB GPU memory at the configured
  2048-token context. Its measured cold start was about 56 seconds; warm
  Spanish/German requests completed in about 1.5-2.5 seconds. The ignored local
  `.env` enables this model while the versioned example remains opt-in.
- Evidence: `cleanup.py` constrains output, bounds context and falls back on
  HTTP/timeout errors. Protocol v1 carries `audio.level` and
  `session.configure`; the overlay exposes both functions without persistence.
