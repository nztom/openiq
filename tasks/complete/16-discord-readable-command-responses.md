# Readable Discord command responses

Priority: P2  
Owner: unassigned

## Problem

Normal Discord slash-command replies expose internal record IDs, timestamps, and
raw JSON instead of concise operator-facing results. Gear lookup and update are
particularly difficult to read.

## Scope

- Present gear lookup, gear update, and roster setup results with names and
  relevant fields only.
- Preserve the existing structured domain/API result and safe generic fallback
  for other commands.
- Add focused response-formatting tests.

## Non-goals

- Changing gear data, permissions, command options, or Discord delivery rules.
- Reformatting every command response in this task.

## Dependencies

- Task 15 embedded Discord bot runtime.

## Acceptance criteria

- Gear replies show a member name and AP/AAP/DP/score without UUIDs or
  timestamps.
- A missing gear record has an actionable, plain-language reply.
- Roster setup reports additions and inactive members clearly.
- Focused tests cover the presentation paths and existing response limits stay
  intact.

## Validation

- Run focused Discord response and command tests on Linux.
- Review the code for Windows-compatible Python behavior; runtime uses no
  platform-specific behavior.

## Implementation progress

- Gear lookup, update, and list replies now show member-facing values rather
  than record metadata. Roster setup has a concise summary, and a missing member
  points users to autocomplete.
- `guilds.test_discord_responses` passes on Linux. The unrelated existing
  `test_autocomplete_is_scoped_and_private` command test did not complete within
  a 20-second bounded run and needs separate investigation; this formatter does
  not alter autocomplete code.
