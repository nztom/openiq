# Backup, restore, and upgrade rehearsal

Priority: P1  
Owner: Codex  
Depends on: 02-production-host-rehearsal

## Problem

Backup, restore, and upgrade tooling is implemented but lacks rehearsal evidence
on the selected storage and host configuration.

## Scope

- Perform an off-host scheduled backup and restore it into a fresh installation.
- Rehearse failed-upgrade recovery using representative disposable data.
- If PostgreSQL is selected, validate native restore/concurrency behavior with
  matching server and client versions.

## Acceptance criteria

- A dated record proves restore and rollback steps, timings, and data checks.
- The runbook accurately covers selected storage, database, and recovery paths.

## Validation

Use disposable representative data and retain the rehearsal record without
committing private backup contents.
