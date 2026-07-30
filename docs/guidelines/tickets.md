# Ticket guidelines

Tickets are Markdown files and the source of truth for planned repository work.

## Naming

Use `SUB-NNN-short-kebab-case-title.md`. Numbers are never reused. Moving a
ticket between state directories must not change its filename.

## Required content

- status and priority;
- objective and user value;
- scope and explicit non-goals;
- dependencies;
- acceptance criteria with checkboxes;
- technical notes when they constrain implementation;
- verification evidence before completion.

## States

- `backlog`: proposed, refined or ready work;
- `in-progress`: actively owned work;
- `done`: all acceptance criteria verified.

Only one copy of a ticket may exist. Use version-control history rather than
duplicating a file. If work is blocked, keep it in `in-progress` and record the
blocker. A ticket may return to `backlog` if implementation has not started.

## Scope control

Acceptance criteria describe observable outcomes, not implementation activity.
Do not add unrelated cleanup to a ticket. Create a follow-up ticket and link it
under `Related`. Security or privacy defects discovered during work must be
recorded immediately and prioritized before release.

