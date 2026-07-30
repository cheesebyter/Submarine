# Observability and performance guidelines

Use structured local logs with timestamp, level, component, event and correlation
identifier. Content fields must not contain captured speech or translated text by
default.

Track at least:

- capture and session state transitions;
- queue depth and dropped audio frames;
- speech segment duration;
- inference and cleanup latency;
- model load state and GPU out-of-memory errors;
- reconnect attempts and protocol errors.

Development diagnostics must be switchable without changing code. Set bounded log
rotation before enabling file logs. Performance changes require measurements using
the same fixture and configuration before and after the change.

