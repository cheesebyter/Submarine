# Submarine

Submarine is a local-first live translation application for Windows. It captures
an explicitly selected Chrome tab, microphone, physical output or virtual audio
device, translates speech to English on a local NVIDIA GPU, and displays
continuously updated subtitles in a native overlay.

Captured audio and transcripts stay in memory and on the local machine. There
is no telemetry or cloud fallback.

> [!IMPORTANT]
> Submarine is a Experiment. Review the privacy model and known
> limitations before using it with sensitive conversations.

## Current capabilities

- Windows 11 with an NVIDIA CUDA-capable GPU
- Explicit capture of one Chrome tab
- Explicit microphone capture
- WASAPI output-loopback capture for speakers, headphones and virtual devices
- Automatic source-language detection
- English-only target language
- Local inference with `faster-whisper`
- Optional final-sentence cleanup through the local Ollama API
- Provisional and final live subtitles in a resizable always-on-top overlay
- Local-only, schema-validated WebSocket transport
- Bounded queues, connection admission and handshake deadlines

Additional browsers, translation targets, signed installers, automatic updates
and transcript export are not currently supported.

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

## Local data flow

```text
Chrome tab / microphone / selected Windows output or virtual device
  -> Chrome extension or native capture agent (PCM audio)
  -> localhost WebSocket
  -> VAD and segmenter
  -> faster-whisper / CUDA (English translation)
  -> optional Ollama sentence cleanup
  -> desktop subtitle overlay
```

See [docs/architecture/overview.md](docs/architecture/overview.md) for component
boundaries, [docs/architecture/protocol-v1.md](docs/architecture/protocol-v1.md)
for the streaming contract and [tickets/README.md](tickets/README.md) for the
implementation backlog.

## Development setup

### Prerequisites

- Windows 11 with PowerShell 7 or Windows PowerShell 5.1
- Python 3.12 available through `py -3.12`
- Node.js 22 and npm 10
- Google Chrome with extension developer mode available
- NVIDIA RTX GPU with a current driver
- Ollama on loopback when optional sentence cleanup is enabled

CUDA libraries and model files are not required by the backend skeleton. Their
project-local runtime packages are installed by the setup script. Models must
never be downloaded silently during a translation session.

### Bootstrap

```powershell
.\scripts\setup.ps1
.\scripts\download-whisper-model.ps1
.\scripts\check.ps1
```

The setup script creates `.venv`, installs the pinned Python development
dependencies and installs the pinned npm workspace dependencies. No Python or npm
package is expected to be installed globally. The model download is an explicit,
multi-gigabyte one-time step.

### Run the backend

```powershell
.\scripts\dev-backend.ps1
```

The service listens only on `127.0.0.1:8765`. Its content-safe health endpoint is
available at `http://127.0.0.1:8765/health`; `model_status` must be `ready` before
starting capture. The normal command runs without file watching so Whisper stays
loaded. During active backend development, opt into automatic restarts with
`.\scripts\dev-backend.ps1 -Reload`.

### Load the Chrome extension

```powershell
npm run build
```

Open `chrome://extensions`, enable **Developer mode**, choose **Load unpacked**
and select `apps/chrome-extension/dist`. Start the backend before pressing
**Start translation** in the extension popup.

### Run the subtitle overlay

In a second PowerShell window:

```powershell
.\scripts\dev-overlay.ps1
```

The native resizable overlay connects only to `127.0.0.1`, stays on top by
default and shows provisional text in gray italics until finalized English text
replaces it. `A-` and `A+` change the font size. The source-language selector
can lock Whisper to Spanish, German, French, Italian or Portuguese when
automatic detection is unreliable. The audio meter and a warning after three
seconds of silence distinguish missing tab audio from missing speech.
**Stop capture** terminates the active Chrome capture session. Closing the
window disconnects the overlay cleanly; subtitles remain only in bounded memory
and are never saved.

The **Windows audio source** selector also lists WASAPI microphones and complete
output-device mixes. Choose a microphone or an `Output — ...` entry and press
**Start source**. Output entries capture everything Windows sends to that
headphone, speaker or virtual output. Virtual devices such as VB-CABLE,
VoiceMeeter, SteelSeries Sonar and NVIDIA Broadcast use the same selection path.
Only one Chrome or Windows source may be active at a time.

Final-sentence cleanup through local Ollama is disabled by default. Copy the
corresponding values from `config/.env.example` into the ignored root `.env` to
enable it. Provisional subtitles never use Ollama, and errors or timeouts fall
back to the raw Whisper result. `translategemma:4b` is the recommended cleanup
model; Submarine limits its context to 2048 tokens to avoid unnecessary VRAM
use beside Whisper.

### Ticket workflow

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

## Security and privacy

- Runtime services are restricted to loopback IP addresses.
- Browser origins are rejected at native-only WebSocket endpoints.
- Protocol messages, audio frames, queues and concurrent subtitle connections
  are bounded.
- Raw audio and full transcripts are not logged or persisted by default.
- Model downloads are explicit setup operations, never runtime fallbacks.

Please report suspected vulnerabilities privately through the process in
[SECURITY.md](SECURITY.md). Do not include audio,
transcripts, tokens, `.env` content or personal paths in public issues.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the ticket workflow, development
checks and pull-request requirements.

## License

Submarine is available under the [MIT License](LICENSE).
