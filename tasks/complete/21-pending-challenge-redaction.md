# Keep challenge rolls hidden until acceptance

Priority: P2  
Owner: Codex

## Problem

`views.state` hides a pending challenge roll, but `operations.challenge`
returns `public(record)` and shared response filtering removes only notes.
On 2026-09-17, a member creating a challenge received its pending roll in the
action result. A caller can inspect rolls and selectively issue challenges.

## Scope

Exclude unresolved rolls from public action responses as well as state
responses, without erasing the stored roll needed for acceptance.
Non-goal: redesigning the minigame or randomness.

## Dependencies

None.

## Acceptance criteria

- Creation and pending state never disclose the hidden roll to either player.
- Acceptance still resolves from the original stored roll.
- Completed challenge results remain readable.

## Validation

Cover member HTTP create/state/accept responses and shared-service responses;
assert the pending value exists only in storage.
Run relevant automated regressions on Linux before completion.

## Implementation status

- Public record serialization now removes the stored roll from pending
  challenges for every caller and transport; the state view uses that shared
  behavior instead of a view-only special case.
- Acceptance still reads the original stored roll, and completed responses and
  state expose both rolls and the winner.
- Linux validation on 2026-09-21 passed the focused service/HTTP challenge test,
  88 domain, workflow, permission, and component tests, `manage.py check`, and
  `git diff --check`.
