# Reject roster values that break dashboard rendering

Priority: P1  
Owner: Codex

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
Run relevant automated regressions on Linux. This is server-side behavior, so
Windows runtime validation is not required.

## Implementation status

- Roster create/edit now validates and normalizes character, class, group,
  specialization, active, exception and class-backfill values before writing.
- Added read-only `validate_roster` diagnostics and operator instructions for
  finding legacy malformed rows and correcting them through the authorized
  roster edit path.
- Added focused service and HTTP coverage for malformed types, bounds, useful
  400 responses, rollback, partial edits, empty optional fields, diagnostics,
  repair and a successful analytics load after rejection.

## Validation evidence

- Linux: `python manage.py test guilds.test_roster_validation
  guilds.test_workflows guilds.tests` — 89 tests passed.
- Linux: `python manage.py check` and `git diff --check` passed.
- Live read-only validation: all four Pi Swarm nodes were Ready, `openiq_web`
  was 1/1, and `https://openiq.pirate.nz/healthz/` plus `/readyz/` reported OK;
  readiness included database, migrations, storage and bot. The live image was
  the pre-change revision, so no production mutation test was attempted.
- The full local suite stalls in the existing
  `ClusterBoundaryTests.test_shared_server_roles_records_and_allied_server_boundaries`
  async autocomplete path; no failure was reported before stopping it.

## Completion

Completed. The maintainer clarified that Windows runtime validation applies to
live desktop capture and other OS-facing behavior, not this web/server change.
