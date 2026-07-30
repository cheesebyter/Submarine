# Security Policy

## Supported Versions

Security fixes are developed for the current `main` branch. Tagged releases
will be listed here once public releases exist.

## Reporting a Vulnerability

Do not open a public issue. Use GitHub Private Vulnerability Reporting:
https://github.com/cheesebyter/Submarine/security/advisories/new

Do not include unnecessary audio, transcripts, credentials, `.env` content or
personal paths. Maintainers will acknowledge a report within 7 days, provide a
triage update within 14 days, and coordinate disclosure after a fix is ready.

## System and Scope

Submarine is a local-first Windows application covering the Chrome extension,
native overlay and audio capture, loopback FastAPI backend, shared protocol,
local faster-whisper inference, optional loopback Ollama cleanup, setup scripts
and release automation.

## Threat Model and Trust Boundaries

Captured audio, live transcripts, capture controls and workstation resources
are protected assets. Malicious web pages, unprivileged local processes,
malformed media and protocol clients are in scope. The local administrator,
operating system and explicitly installed local models are trusted. Runtime
services are not intended to be reachable beyond loopback.

## Security Invariants

- Services bind only to loopback IP addresses.
- Capture requires explicit user action and remains visibly stoppable.
- Browser and native WebSocket client classes are separated before admission.
- Protocol input, connections, queues, frames, inference work and timeouts are bounded.
- A client cannot control another session merely by knowing a public identifier.
- Audio and transcripts stay ephemeral and off remote networks by default.
- No secrets, recordings, logs, model weights or local configuration enter releases.

## Reportable Findings and Severity Context

Report unauthorized capture, transcript disclosure, cross-origin or cross-session
control, non-loopback exposure, code execution, meaningful resource exhaustion,
secret publication and remote processing that violates the local-only promise.
Loopback-only reachability lowers severity but does not make browser or
lower-privileged local boundary violations non-reportable.

## Out of Scope, Exclusions, and Accepted Risk

A malicious administrator or compromised operating system is out of scope.
Expected model inaccuracies, hallucinations and translation quality problems are
not security issues without a separate boundary or safety impact. Denial of
service requiring administrator access or already-equivalent host compromise is
normally out of scope.

## Known Limitations and Compensating Controls

The project is pre-release, supports Windows 11 and has no signed installer or
auto-update channel. Browser private-network policy varies. Loopback binding,
origin checks, bounded admission, schema validation and ephemeral processing are
defense layers, not proof that every local client is trusted.
