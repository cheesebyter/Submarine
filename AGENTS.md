# AGENTS.md

These instructions apply to the entire Submarine repository. A more specific
`AGENTS.md` in a subdirectory may add or override instructions for that subtree.

## Mission

Build a reliable local-first Windows application that captures user-selected
application audio and produces live English subtitles. The MVP supports Google
Chrome first. Privacy, responsiveness and understandable failure states are
product requirements, not optional refinements.

## Required workflow

1. Read `README.md`, the relevant architecture documents and the selected ticket.
2. Work on one ticket at a time unless the tickets explicitly permit parallel work.
3. Move the ticket from `backlog` to `in-progress` before implementation.
4. Keep changes scoped to the ticket. Record newly discovered work as a separate
   ticket instead of silently expanding scope.
5. Add or update tests with behavioral changes.
6. Run the narrowest relevant checks first, followed by the component test suite.
7. Update documentation and configuration examples when behavior changes.
8. Record verification evidence in the ticket.
9. Move the ticket to `done` only when every acceptance criterion is satisfied.

## Engineering rules

- Follow all documents under `docs/guidelines/`.
- Keep Chrome capture, transport, inference and presentation behind explicit
  interfaces. Avoid importing one application directly into another.
- Treat `packages/protocol` as the canonical cross-component contract.
- Use typed data structures and validate all data at process boundaries.
- Bind development services to loopback by default.
- Never introduce a cloud dependency, telemetry, remote model download at
  runtime, or external network call without an explicit approved ticket.
- Do not commit model weights, audio recordings, transcripts, logs, secrets,
  generated build output or machine-specific configuration.
- Do not log raw audio. Transcript logging must be off by default.
- Keep provisional and final transcript states distinct throughout the system.
- Prefer deterministic configuration over hidden environment-dependent behavior.

## Change safety

- Preserve user changes and unrelated working-tree modifications.
- Do not delete or rewrite user data without explicit authorization.
- Schema and protocol changes require backward-compatibility consideration and
  corresponding integration tests.
- Changes affecting audio capture, privacy, firewall behavior, installation or
  model acquisition require explicit manual verification notes.

## Definition of done

A change is done only when:

- acceptance criteria pass;
- relevant automated tests and static checks pass;
- failure behavior is tested or manually verified;
- documentation and example configuration are current;
- privacy and security implications were considered;
- the ticket contains verification evidence and no unresolved checklist item.

