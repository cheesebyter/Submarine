# SUB-009: Suppress repeated subtitle hallucinations

- Status: Done
- Priority: P0
- Owner: Unassigned
- Depends on: SUB-004, SUB-005

## Objective

Prevent repeated Whisper phrases and duplicate short finalized segments from
overwhelming the live subtitle overlay.

## Scope

- Collapse consecutive repeated multi-word phrases before and after cleanup.
- Bound implausibly long output relative to captured audio duration.
- Deduplicate normalized adjacent final subtitles in the overlay.
- Preserve legitimate single-word emphasis.

## Acceptance criteria

- [x] Multi-word repetition loops collapse to one occurrence.
- [x] Short repeated final segments do not create duplicate history entries.
- [x] Ordinary sentences and single-word emphasis remain intact.
- [x] Provisional and final behavior remains distinct.

## Verification

- Automated: Full check passes with 43 backend, 7 overlay and 29 TypeScript
  tests. Regression tests cover repeated phrase loops, output bounds,
  punctuation/case duplicates and legitimate repeated single words.
- Manual: The repeated six-word pattern shown in the reported failure collapses
  deterministically to one occurrence.
- Evidence: Sanitization runs before and after optional Ollama cleanup; the
  overlay independently normalizes adjacent final history entries.
