# Deployment and release guidelines

## Environments

- Development runs from source with explicit local configuration.
- Release builds are reproducible and versioned.
- Runtime services bind to loopback unless a future approved design says otherwise.

## Versioning

Use Semantic Versioning after the first tagged release. Before `1.0.0`, minor
versions may contain breaking changes but must include migration notes.

## Release requirements

- clean build from a fresh checkout;
- automated tests, type checks and linters pass;
- supported Windows and Chrome versions are documented;
- model and CUDA prerequisites are documented and checked;
- extension and backend protocol versions are compatible;
- no secrets, recordings, transcripts or model weights are packaged;
- privacy and network behavior are manually verified;
- rollback or uninstall steps are documented;
- release notes identify known limitations.

## Model handling

Model acquisition is an explicit setup step. Pin model identity and revision where
possible, verify expected files, and show disk requirements. Never download or
switch models silently during a translation session.

## Artifacts

Generate artifacts into ignored directories. Attach checksums to published
packages. Signing and installer strategy require a dedicated ticket before public
distribution.

