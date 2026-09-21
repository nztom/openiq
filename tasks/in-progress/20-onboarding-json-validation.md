# Reject malformed onboarding JSON without server errors

Priority: P2  
Owner: Codex

## Problem

`views.onboard` calls `.get` on parsed JSON before validating its shape. An
authenticated POST of `[]` to `/onboard/` returned HTTP 500 in a disposable
reproduction on 2026-09-17. JSON null and other scalars need the same guard.

## Scope

Validate the onboarding request object before reading its fields and preserve
the existing atomic creation and Discord authority checks. Non-goal: changing
onboarding UX or adding a general schema framework.

## Dependencies

None.

## Acceptance criteria

- Valid JSON with a non-object top level returns a clear JSON 400.
- Malformed bodies create no guild, membership or roster records.
- Valid onboarding and authorization failures preserve their documented behavior.

## Validation

Use authenticated request tests for array/null/string/number bodies, malformed
JSON, missing fields, and valid onboarding in local and production modes.
Run relevant automated regressions on Linux before completion.
