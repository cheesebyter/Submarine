# Submarine tickets

Tickets move through `backlog`, `in-progress` and `done`. See
`docs/guidelines/tickets.md` for the workflow and `_template.md` for required
fields.

## Initial implementation order

1. `SUB-001` — backend and development bootstrap
2. `SUB-002` — versioned streaming protocol
3. `SUB-003` — Chrome tab audio capture
4. `SUB-004` — local Whisper translation pipeline
5. `SUB-005` — live subtitle overlay
6. `SUB-006` — optional Ollama cleanup
7. `SUB-007` — end-to-end hardening and MVP packaging
8. `SUB-010` — open-source security hardening
9. `SUB-011` — native-client session capabilities

Tickets may overlap only when their dependencies are satisfied and their changed
files do not conflict.
