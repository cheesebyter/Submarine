# Security hardening verification

This checklist covers the local WebSocket and publication boundaries added for
the first public source release.

## Automated checks

Run from the repository root:

```powershell
.\scripts\check.ps1
.\scripts\publication-check.ps1
.\.venv\Scripts\python.exe -m pip_audit --local
npm audit --audit-level=high
```

The subtitle regression suite verifies:

- originless native overlay connections remain functional;
- browser-origin subtitle connections fail with WebSocket policy code `1008`;
- no subscriber queue exists before a valid hello;
- silent pre-hello connections close after the deadline;
- connection capacity is enforced with retry-later code `1013`;
- reservations and subscriber queues are released after disconnect.

## Manual release checks

1. Start the backend without reload and confirm it binds only to
   `127.0.0.1:8765`.
2. Start the overlay and verify it receives backend health and subtitles.
3. Start and stop each supported source: Chrome tab, microphone, physical output
   and one installed virtual device when available.
4. Confirm Task Manager and browser developer tools show no remote destination
   for audio or transcript traffic.
5. Stop the backend while the overlay is connected; confirm the overlay reports
   a content-safe local error and reconnects after restart.
6. Inspect the publication candidate list for recordings, models, `.env` files,
   logs, tokens and machine-specific paths.

Do not use personal or sensitive audio for release verification.
