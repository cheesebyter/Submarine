# Submarine streaming protocol v1

Protocol version 1 runs over a local WebSocket. JSON text frames carry control
messages; binary frames carry audio. The canonical JSON Schema is
`packages/protocol/src/control-message.schema.json`.

## Limits

- control frame: at most 16 KiB after UTF-8 encoding;
- audio frame: exactly 660 bytes;
- transcript text: at most 8192 Unicode characters;
- identifiers: 1–64 ASCII letters, digits, underscores or hyphens.

The receiver closes a connection that repeatedly violates limits. It must never
buffer an unbounded partial message.

## Negotiation

The first control message is `hello` with `protocolVersion: 1` and a client type.
Messages with any other version receive `unsupported_version`; v1 has no
downgrade mechanism. A client should then stop and display an update-required
error.

The backend requires the subtitle hello within five seconds and admits at most
four concurrent subtitle connections. Browser `Origin` headers are rejected on
native-only capture and subtitle routes before WebSocket acceptance. Protocol
v1 does not cryptographically authenticate same-user native processes.

## Session lifecycle

```text
idle -> session.start -> starting
starting -> session.started -> streaming
streaming -> session.stop -> stopping
stopping -> session.stopped -> stopped
stopped -> session.start -> starting (new session)
```

Health and error messages do not change session state. Other transitions are
invalid. A source may send binary audio only while streaming.

`transcript.provisional` may be replaced by another provisional event with the
same sequence. `transcript.final` commits that sequence permanently. Clients
must ignore a later provisional event for a finalized sequence.

## Binary audio frame

All integer fields are unsigned little-endian.

| Offset | Size | Field | Value |
| ---: | ---: | --- | --- |
| 0 | 4 | magic | ASCII `SUBA` |
| 4 | 1 | protocol version | `1` |
| 5 | 1 | flags | `0`, reserved |
| 6 | 2 | header length | `20` |
| 8 | 4 | sequence | wraps after `2^32 - 1` |
| 12 | 8 | session-relative timestamp | milliseconds |
| 20 | 640 | PCM payload | 20 ms, 16 kHz, mono, signed 16-bit LE |

Sequence gaps indicate dropped frames. Timestamps are monotonic within a session.

## Reconnect and termination

Sessions are not resumed in v1. After a disconnect, the backend releases buffered
audio and session state. A reconnect performs `hello` and `session.start`, receives
a new session ID and resets audio and transcript sequences.

For an orderly shutdown, the capture client sends `session.stop` and waits up to
two seconds for `session.stopped`. On timeout or connection loss, it closes the
socket and stops capture locally. The server may use `server-shutdown` when it
initiates termination.

## Error safety

Error text is user-actionable but contains no audio, transcript, token, prompt or
machine-specific path. `recoverable` indicates whether retrying without changing
the request can succeed.
