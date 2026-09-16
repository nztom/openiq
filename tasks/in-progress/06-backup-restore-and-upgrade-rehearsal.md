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

## Implementation progress

2026-09-16: The main container now runs the backup scheduler only when its
`BACKUP_OUTPUT` directory exists (default `/backups`), with a four-hour default
interval. The separate Compose backup service has been removed. The Pi-cluster
Swarm definition and Pi-side build/deploy script are in `/mnt/data/swarm/openiq`.
Focused backup tests and the complete Python suite pass with 100% coverage.

Remaining: build and deploy the ARM image on a Pi, then run the disposable
off-host backup, isolated restore, and failed-upgrade recovery rehearsal.
