# Reject roster values that break dashboard rendering

Priority: P1  
Owner: unassigned

## Problem

`roster.save` stores unvalidated `class`, `character`, `group`, `spec`, and
boolean fields. On 2026-09-17, an officer POST containing `{"name":"Broken",
"class":[]}` returned HTTP 200; the next guild state GET returned HTTP 500
because `analytics.calculate` uses the class as a dictionary key. This makes
the dashboard unavailable to the whole guild until the record is repaired.

## Scope

Validate editable roster field types and bounds before persistence, preserving
partial edits and legitimate empty optional fields. Provide a bounded repair
path for existing malformed rows. Non-goal: redesigning roster storage.

## Dependencies

None.

## Acceptance criteria

- Invalid create/edit payloads return a useful 400 without writes.
- Supported roster edits keep analytics and browser rendering usable.
- Existing malformed records can be identified and corrected safely.

## Validation

Cover list/object/null values, invalid booleans, valid partial edits, rollback,
and a successful guild state load after rejected input.
Run relevant automated regressions on Linux and Windows before completion.
