# Submarine

Submarine is a local-first live translation application. The MVP captures audio
from an active Google Chrome tab, transcribes and translates speech to English
on the local NVIDIA GPU, and displays continuously updated subtitles.

No captured audio or transcript should leave the machine.

## MVP scope

- Windows 11 and Google Chrome
- Explicit capture of one Chrome tab
- Automatic source-language detection
- English-only target language
- Local inference with `faster-whisper`
- Optional final-sentence cleanup through the local Ollama API
- Provisional and final live subtitles

System-wide and per-application audio capture, additional browsers, translation
targets, installers, and transcript export are post-MVP features unless a ticket
explicitly adds them.

## Repository layout

```text
apps/
  chrome-extension/       Chrome Manifest V3 capture client
  desktop-overlay/        Local subtitle user interface
services/
  translation-backend/    Audio, transcription, translation and session service
packages/
  protocol/               Shared WebSocket message and data contracts
config/                   Versioned non-secret configuration examples
docs/
  architecture/           Architecture decisions and system design
  guidelines/             Development and operational rules
scripts/                  Repeatable setup, development and release scripts
tests/
  integration/            Tests spanning multiple components
tickets/
  backlog/                Ready or proposed work
  in-progress/            Work currently being implemented
  done/                   Completed and verified work
var/
  logs/                   Local runtime logs; ignored by Git
  models/                 Local model files; ignored by Git
```

## Planned local data flow

```text
Chrome tab
  -> Chrome extension (PCM audio)
  -> localhost WebSocket
  -> VAD and segmenter
  -> faster-whisper / CUDA (English translation)
  -> optional Ollama sentence cleanup
  -> desktop subtitle overlay
```

See [docs/architecture/overview.md](docs/architecture/overview.md) for component
boundaries and [tickets/README.md](tickets/README.md) for the implementation
backlog.

## Getting started

The repository currently contains the project foundation and ticket backlog.
Runtime setup commands will be added by the bootstrap tickets. Until then:

1. Read `AGENTS.md`.
2. Select the first unblocked ticket from `tickets/backlog/`.
3. Move it to `tickets/in-progress/` before changing code.
4. Follow the relevant documents in `docs/guidelines/`.
5. Move the ticket to `tickets/done/` only after all acceptance criteria pass.

## Core principles

- Local-first privacy
- Low perceived latency
- Clear provisional versus final subtitle state
- Replaceable capture, inference and UI components
- Reproducible setup and releases
- No silent fallback to cloud services

