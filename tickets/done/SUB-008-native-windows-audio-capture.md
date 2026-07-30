# SUB-008: Native Windows microphone and output capture

- Status: Done
- Priority: P0
- Owner: Unassigned
- Depends on: SUB-002, SUB-005

## Objective

Capture a selected Windows microphone or the full mix sent to a selected output
device, including virtual audio devices, and feed it into the existing local
translation pipeline.

## Scope

- Enumerate WASAPI microphones and loopback output devices.
- Select and start a source from the desktop overlay.
- Resample locally to protocol PCM 16 kHz mono frames.
- Reuse the bounded localhost capture protocol.
- Show actionable device and signal errors.
- Stop and release devices cleanly.

## Acceptance criteria

- [x] Physical and virtual microphones can be selected.
- [x] Physical and virtual output loopback devices can be selected.
- [x] Native capture produces protocol-compliant PCM without persistence.
- [x] UI stays responsive during capture.
- [x] Stop and window close release the selected device.

## Verification

- Automated: Overlay formatting, lint, strict mypy and 6 tests pass; backend
  formatting, lint, strict mypy and the 4 capture integration tests pass.
- Manual: WASAPI enumeration found the Arctis physical microphone and headphone
  loopback plus SteelSeries Sonar and NVIDIA Broadcast virtual devices. A
  48-kHz Arctis microphone frame was opened and read successfully; the Arctis
  output loopback stream opened successfully.
- Evidence: `audio_capture.py` enumerates WASAPI only, resamples float input to
  bounded 20 ms PCM frames and owns device cleanup. `/ws/native-capture` reuses
  the validated local protocol without accepting browser origins. No audio is
  written to disk.
