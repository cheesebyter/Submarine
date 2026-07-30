# SUB-002: Define the versioned streaming protocol

- Status: Done
- Priority: P0
- Owner: Codex
- Depends on: SUB-001

## Objective

Create a validated contract for communication between capture clients, backend
and subtitle clients.

## Scope

- Define session, audio, transcript, health and error messages.
- Define audio encoding, sample rate, channel count and frame timing.
- Include protocol-version negotiation and message-size limits.
- Generate or share types across Python and TypeScript where practical.

## Non-goals

- Chrome capture and model inference.

## Acceptance criteria

- [x] Provisional and final transcript events are unambiguous.
- [x] Invalid versions, state transitions and oversized messages are rejected.
- [x] Python and TypeScript validation tests use the same fixtures.
- [x] Reconnect and session termination behavior is documented.

## Verification

- Automated: `.\scripts\check.ps1`
- Manual: Reviewed the v1 lifecycle, reconnect semantics, termination timeout,
  binary frame layout and content-safe error requirements.
- Evidence: 29 Python tests and 22 protocol TypeScript tests pass. Both runtimes
  consume `packages/protocol/fixtures`; control messages, invalid transitions,
  unsupported versions, size limits and binary audio frames are covered. npm
  reports zero known vulnerabilities.
