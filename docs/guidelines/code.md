# Code guidelines

## General

- Optimize for readability and explicit behavior.
- Keep functions focused and components loosely coupled.
- Use English for code, identifiers, comments, logs and technical documentation.
- Prefer immutable values and typed interfaces.
- Validate input at every external boundary.
- Report actionable errors; never discard exceptions silently.
- Avoid premature abstraction, but isolate operating-system and model-specific code.

## Python

- Target a single documented Python version.
- Use type hints for public and internal interfaces.
- Use Ruff for formatting and linting, and pytest for tests.
- Keep blocking inference work out of the async event loop.
- Use structured logging with content-safe fields.

## TypeScript

- Enable strict TypeScript checking.
- Avoid `any`; use `unknown` plus validation for external data.
- Keep extension service-worker, offscreen-document and UI responsibilities separate.
- Use browser APIs behind small adapters to make state logic testable.

## Testing

- Unit-test segmentation, state transitions and protocol validation.
- Add integration tests for WebSocket lifecycle and error recovery.
- Use short generated or explicitly licensed audio fixtures.
- Never add personal recordings or sensitive transcripts to the repository.
- A bug fix must include a regression test when practical.

## Comments and commits

- Comments explain constraints and intent, not obvious syntax.
- Reference a ticket in material commits.
- Keep commits cohesive and avoid mixing formatting-only changes with behavior.

