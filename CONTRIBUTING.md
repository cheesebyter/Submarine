# Contributing to Submarine

Thank you for helping improve local, private live translation.

## Before you start

- Read [AGENTS.md](AGENTS.md) and the applicable files under
  [docs/guidelines](docs/guidelines).
- Search existing issues and tickets before proposing duplicate work.
- Discuss changes that affect the protocol, privacy model, audio capture,
  dependencies or distribution before implementing them.
- Never include personal recordings, transcripts, credentials, model weights,
  logs or machine-specific configuration.

## Development setup

Submarine currently targets Windows 11, Python 3.12, Node.js 22 and Chrome.

```powershell
.\scripts\setup.ps1
.\scripts\check.ps1
```

Model acquisition is a separate explicit step and is not required for most
unit tests:

```powershell
.\scripts\download-whisper-model.ps1
```

## Making a change

1. Create or select one ticket under `tickets/`.
2. Move it to `tickets/in-progress/` and update its status.
3. Keep the change focused and preserve unrelated working-tree changes.
4. Add regression coverage for behavior changes.
5. Update documentation and configuration examples.
6. Run focused checks first, then `.\scripts\check.ps1`.
7. Record verification evidence and move the ticket to `tickets/done/`.

## Pull requests

Pull requests should:

- explain the user-visible outcome and link the ticket or issue;
- identify privacy, security, protocol and compatibility effects;
- include tests for success and failure behavior;
- state which automated and manual checks were run;
- avoid generated builds, local configuration and runtime data;
- keep commits cohesive and use clear English commit messages.

By contributing, you agree that your contribution is licensed under the
repository's [MIT License](LICENSE).

## Security reports

Do not open a public issue for a suspected vulnerability. Follow the private
reporting process described in [SECURITY.md](SECURITY.md).
