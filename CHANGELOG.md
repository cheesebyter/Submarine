# Changelog

All notable changes to Submarine will be documented here. The project follows
[Semantic Versioning](https://semver.org/) after its first tagged release.

## [Unreleased]

### Added

- Chrome tab, Windows microphone, output-loopback and virtual-device capture.
- Local faster-whisper translation to English.
- Optional local Ollama sentence cleanup.
- Native live subtitle overlay with source, status and accessibility controls.
- Security regression coverage and open-source project automation.
- Extended source-language list; the overlay remembers the last choice.
- Opt-in transcript recording (original and English text files) in the overlay.
- Configurable Whisper language, prompts, confidence, VAD and energy-gate settings.
- Glossary-aware Ollama copy-editing prompt for final subtitles.

### Security

- Reject browser origins at the native subtitle WebSocket.
- Bound concurrent subtitle connections and pre-hello duration.
