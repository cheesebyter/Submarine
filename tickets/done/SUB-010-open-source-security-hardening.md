# SUB-010: Harden the open-source release

- Status: Done
- Priority: P0
- Owner: Codex
- Depends on: SUB-003, SUB-004, SUB-005, SUB-008

## Objective

Prepare Submarine for a responsible public GitHub release by closing the
validated local WebSocket findings and adding repository security, contribution,
automation and publication controls.

## Scope

- Reject browser origins at the native subtitle WebSocket boundary.
- Bound subtitle connection count and pre-hello lifetime.
- Add security regression tests for malicious and legitimate clients.
- Add open-source license, contribution, conduct, support and vulnerability
  reporting documentation.
- Add GitHub CI, dependency update configuration and contribution templates.
- Repair stale or corrupted publication documentation and package metadata.
- Verify builds, tests, static checks, dependency state and secret hygiene.

## Non-goals

- Signed installers, store distribution and automatic updates.
- Network or cloud translation.
- Redesigning the versioned streaming protocol beyond required hardening.

## Acceptance criteria

- [x] Browser-origin subtitle connections are rejected before admission.
- [x] Subtitle connections have a global capacity and hello deadline.
- [x] Existing native overlay behavior remains operational.
- [x] Focused security regression tests and all repository checks pass.
- [x] Required open-source and GitHub community files are present.
- [x] Documentation matches the implemented Chrome and Windows audio sources.
- [x] Publication checks find no secrets, recordings, local runtime data or
      machine-specific paths in tracked candidates.

## Technical notes

The authoritative Codex Security scan
`a0206996-488f-46ae-b6ab-7f53635d8b26` reported two Low-severity findings at
`/ws/subtitles`: cross-origin transcript/control access and unbounded subscriber
admission.

## Verification

Complete before moving the ticket to `done`.

- Automated:
  - `.\scripts\check.ps1`: passed.
  - Backend: 47 tests passed; overlay: 7 tests passed.
  - Chrome extension: 7 tests passed; protocol: 22 tests passed.
  - `.\scripts\publication-check.ps1`: 107 publication candidates passed.
  - `python -m pip_audit --local`: 0 known vulnerabilities.
  - `npm audit --audit-level=high`: 0 known vulnerabilities.
  - YAML, JSON, TOML and PowerShell syntax validation: passed.
- Manual:
  - The original cross-origin PoC is rejected before WebSocket admission.
  - The original pre-hello subscriber PoC cannot allocate a subscriber.
  - An originless native subtitle hello still receives backend health.
  - No disruptive connection-load test was run.
- Evidence:
  - Codex Security scan `a0206996-488f-46ae-b6ab-7f53635d8b26`.
  - Scan-local `artifacts/fix_report.md`.
  - `docs/testing/security-hardening.md`.

## Related

- SUB-007
