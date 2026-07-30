# SUB-005: Build the live subtitle overlay

- Status: Done
- Priority: P0
- Owner: Unassigned
- Depends on: SUB-002

## Objective

Display readable live English subtitles and clear local system state.

## Scope

- Select overlay technology through a small documented spike.
- Show provisional and final text distinctly.
- Show connection, capture, language and model status.
- Provide always-on-top, resize, font-size and stop controls.
- Keep a bounded in-memory subtitle history.

## Non-goals

- Transcript persistence, export and multi-monitor layout presets.

## Acceptance criteria

- [x] Provisional text can be replaced without duplicating finalized text.
- [x] The overlay remains responsive while inference is busy.
- [x] Errors state what the user can do next.
- [x] Closing or stopping the overlay terminates its session cleanly.
- [x] No transcript is persisted by default.

## Verification

- Automated: `.\scripts\check.ps1` passes (38 backend tests, 2 overlay
  tests, 27 TypeScript tests, lint, formatting, mypy, TypeScript and builds).
- Manual: Tk 8.6 window construction, resize minimum and clean shutdown smoke
  passed on Windows; the running CUDA backend reported `model_status=ready`.
- Evidence: `apps/desktop-overlay` provides the UI, bounded view model and
  background WebSocket client. `/ws/subtitles` fans out ephemeral events and
  forwards the stop control. Technology decision is recorded in
  `docs/architecture/desktop-overlay-spike.md`.
