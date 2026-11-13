# SUB-012: Reliable source language and opt-in transcript recording

- Status: In progress
- Priority: P1
- Owner: Unassigned
- Depends on: SUB-005, SUB-009

## Objective

Reduce wrong automatic language detection by letting the user fix the source
language (also before capture starts), and let the user explicitly record each
session as two plain-text files: the original-language transcript and the
English translation.

## Scope

- Extend the selectable source languages in the overlay and protocol enum.
- The overlay remembers the last chosen source language (and recording folder)
  in the ignored `var/run/overlay-settings.json`; the backend engine keeps the
  language across sessions until it is reconfigured.
- Add optional `includeOriginal` to `session.configure` and optional
  `originalText` to `transcript.final`. Provisional results never carry it.
- Backend runs an additional `transcribe` pass for final segments only, and
  only while `includeOriginal` is set (no extra GPU cost otherwise).
- Overlay checkbox "Mitschnitt speichern" writes `<timestamp>_original.txt`
  and `<timestamp>_english.txt` (one line per final segment, same line number
  in both files) to a user-selectable folder, default `var/transcripts/`.

## Consent, retention and deletion

- Recording is off by default and starts only through the explicit overlay
  checkbox. A visible "REC" indicator and the target folder are shown while
  active.
- Files are written by the overlay on the local machine only; the backend never
  persists transcripts and never logs them.
- Retention: files stay until the user deletes them. `var/transcripts/` is
  ignored by Git. Deletion is manual (no automatic deletion).
- Unchecking the box or closing the overlay closes the files immediately.

## Non-goals

- Subtitle formats (SRT/VTT) and timestamps per line.
- Recording of provisional text.
- Automatic cleanup of old transcript files.

## Acceptance criteria

- [x] Source language can be chosen from an extended list and is remembered.
- [x] Recording is opt-in, visibly indicated and writes two aligned files.
- [x] No extra inference happens when recording is off.
- [ ] Protocol schema, TypeScript types and fixtures stay in sync (TS tests pending on Windows).
- [x] Documentation and `.env.example` are current.

## Verification

- Automated: 52 backend tests (incl. fixtures with the new optional fields and
  original-text on/off/failure cases) and the new overlay recorder/settings tests
  pass; ruff clean on changed code. `npm test`/`check.ps1` still to be run on Windows.
- Manual: Pending — run a Spanish/German source with the language locked and
  recording on; compare line counts of both files.
- Evidence: Pending manual run.

## Related

- SUB-004, SUB-005, SUB-009
