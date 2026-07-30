# SUB-001: Bootstrap development environment

- Status: Done
- Priority: P0
- Owner: Codex
- Depends on: None

## Objective

Provide a reproducible Windows development setup and a runnable backend skeleton.

## Scope

- Pin Python and Node.js requirements.
- Add backend dependency management and quality-tool configuration.
- Add extension TypeScript build configuration.
- Add setup, check and development scripts.
- Add a backend health endpoint with no content-sensitive output.
- Document NVIDIA, CUDA, Ollama and Chrome prerequisites.

## Non-goals

- Audio capture, inference and production packaging.

## Acceptance criteria

- [x] A fresh supported Windows machine can follow documented setup steps.
- [x] One command runs formatting, linting, type checks and tests.
- [x] The backend starts locally and its health endpoint responds.
- [x] No dependency or tool relies on an undocumented global installation.

## Verification

- Automated: `.\scripts\check.ps1`
- Manual: Setup executed on Windows 11 with Python 3.12, Node.js 22 and npm 10.
- Evidence: Ruff, mypy, pytest, TypeScript, Vitest and the extension build pass.
  The TCP smoke test starts Uvicorn on an ephemeral loopback port, requests
  `/health`, verifies the response and confirms clean shutdown.
