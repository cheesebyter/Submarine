# SUB-003: Capture Chrome tab audio

- Status: Done
- Priority: P0
- Owner: Codex
- Depends on: SUB-001, SUB-002

## Objective

Let the user explicitly start and stop capture of the active Chrome tab while
continuing to hear its audio.

## Scope

- Minimal-permission Manifest V3 extension.
- `chrome.tabCapture` flow and offscreen audio processing.
- Resampling and streaming in the agreed protocol format.
- Capture status, stop action and actionable errors.

## Non-goals

- Capturing arbitrary desktop applications or the microphone.

## Acceptance criteria

- [x] Capture begins only after a user gesture.
- [x] Tab audio remains audible during capture.
- [x] Audio reaches a local test receiver in the agreed format.
- [x] Capture stops on request and when the source becomes unavailable.
- [x] Connection failure does not create an unbounded memory queue.

## Verification

- Automated: `.\scripts\check.ps1`
- Manual: User verified capture start/stop in Chrome and confirmed that the
  captured tab remained audible. Source-tab closure follows the same documented
  stop path and was included in the executed checklist. Reopened after the popup
  status request stalled because Chrome API enum values were referenced as
  runtime objects. A subsequent stale offscreen-context error led to removing
  offscreen messaging from the initial status path. The start path now tolerates
  Chrome's offscreen listener-registration race with a bounded one-second retry.
  The remaining module-load failure was traced to AJV runtime schema compilation,
  which violates Manifest V3 CSP. The Chrome bundle now imports CSP-safe protocol
  types and uses a narrow server-response parser. Extension version 0.1.3 was
  manually verified with the `ON` badge, active stop control, audible source tab
  and an accepted `/ws/capture` backend connection.
- Evidence: 32 Python tests, 5 extension tests and 22 protocol tests pass. The
  extension build produces a complete Manifest V3 bundle. Tests cover 48 kHz to
  16 kHz resampling, PCM framing, bounded drop-oldest buffering, Chrome-origin
  enforcement and a real WebSocket handshake/audio/stop cycle.
