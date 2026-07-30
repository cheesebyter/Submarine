# Architecture overview

## Components

### Chrome extension

Captures audio only after an explicit user action using `chrome.tabCapture`,
continues local playback, converts audio to the agreed wire format and streams it
to the loopback backend. It owns capture permissions and capture state, but no
inference logic.

### Translation backend

Owns sessions, WebSocket transport, buffering, voice activity detection,
segmentation, faster-whisper inference and optional Ollama cleanup. It exposes
health and capability information without exposing captured content.

### Desktop overlay

Displays connection state, detected language, provisional text, final text and
actionable errors. It must remain usable when Ollama cleanup is disabled.

### Shared protocol

Defines versioned messages exchanged between clients and the backend. Messages
must distinguish session lifecycle, audio frames, provisional transcripts, final
transcripts, health information and errors.

## Trust boundary

All runtime traffic remains on the local machine. The backend binds to loopback
only. Chrome capture accepts Chrome-extension origins, while native capture and
subtitle endpoints reject browser origins. Native clients are not
cryptographically authenticated in protocol v1, so connection capacity,
handshake deadlines and the same-user local-process assumption remain relevant.
No component silently connects to a cloud API.

## Initial technology direction

- Chrome Extension: Manifest V3, TypeScript
- Backend: Python, FastAPI/WebSocket, faster-whisper, CUDA
- Translation: Whisper `task=translate`, target English
- Cleanup: optional Ollama HTTP API on loopback
- Overlay: Python/Tkinter with native WASAPI capture
- Audio wire format: mono PCM, 16 kHz, format finalized in the protocol ticket

Technology choices may change through an architecture decision record (ADR).

## Performance targets

Targets are measured on the development RTX 4090 system:

- visible provisional output: ideally within 2 seconds of speech;
- finalization: within 1 second after detected sentence-ending silence;
- no unbounded audio or transcript queue growth;
- at most four concurrent subtitle connections, with a five-second hello
  deadline;
- graceful degradation when Ollama is unavailable.

These are initial targets and must be replaced with measured baselines.
