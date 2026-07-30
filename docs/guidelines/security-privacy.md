# Security and privacy guidelines

- Audio and transcripts are sensitive user data.
- Capture starts only after explicit user action and must have a persistent visual
  indicator plus an immediate stop control.
- Capture stops on stream failure, tab closure or user request.
- Default operation is local-only; cloud fallback is forbidden.
- Bind services to `127.0.0.1`/`::1` and validate WebSocket origins.
- Prefer short-lived session credentials between the extension, overlay and
  backend. Until protocol v1 gains native-client credentials, reject browser
  origins and enforce strict connection and handshake bounds.
- Do not expose Ollama or the translation backend to the LAN.
- Do not log raw audio, prompts or full transcripts by default.
- Redact paths, tokens and captured content from diagnostic bundles.
- Minimize Chrome permissions and justify each permission in documentation.
- Validate message sizes, sample rates and session state to prevent resource abuse.
- Apply bounded queues, request timeouts and clean cancellation.
- Dependencies and packaged binaries must be pinned and reviewed before release.
- Temporary audio buffers stay in memory where practical and are cleared after use.

Any feature that persists, exports or shares transcripts needs an explicit ticket
covering consent, retention and deletion behavior.
