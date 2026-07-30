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

### Security

- Reject browser origins at the native subtitle WebSocket.
- Bound concurrent subtitle connections and pre-hello duration.
