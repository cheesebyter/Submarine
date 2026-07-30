# SUB-011: Authenticate native client capabilities

- Status: Backlog
- Priority: P1
- Owner: Unassigned
- Depends on: SUB-010

## Objective

Prevent an unrelated same-user local process from subscribing to live
transcripts or controlling a capture session merely by connecting to the
loopback service.

## Scope

- Define a short-lived native-client capability lifecycle.
- Deliver capabilities without exposing them to browser origins or logs.
- Bind subtitle subscription and control messages to the intended session.
- Rotate and clear credentials on backend restart and session termination.
- Add integration tests for missing, invalid, expired and cross-session tokens.

## Non-goals

- Defending against a malicious administrator or compromised operating system.
- Remote account identity or cloud authentication.

## Acceptance criteria

- [ ] A same-user process without the capability cannot read transcript events.
- [ ] A public session ID is insufficient for stop or configuration operations.
- [ ] Capabilities are never logged, persisted in release artifacts or exposed
      through content-safe health responses.
- [ ] Normal Chrome and Windows capture workflows remain usable.

## Technical notes

Protocol v1 currently separates browser and native clients through Origin policy
and bounds connections, but it does not cryptographically authenticate
originless same-user processes.

## Verification

Complete before moving the ticket to `done`.

- Automated:
- Manual:
- Evidence:

## Related

- SUB-010
