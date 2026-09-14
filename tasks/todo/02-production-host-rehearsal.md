# Production-host rehearsal and recovery evidence

Priority: P1  
Owner: unassigned  
Depends on: 01-release-automation-and-image-validation

## Problem

Operational commands exist, but deployment assumptions have not been verified
on the Ubuntu host that will run OpenIQ.

## Scope

- Validate TLS termination, DNS, firewall, host allowlists, volumes, process
  profiles, graceful shutdown, readiness, and alert routing.
- Rehearse an off-host scheduled backup, restore to a fresh installation, and
  failed-upgrade recovery.
- If PostgreSQL is selected, run native restore/concurrency tests with matching
  server/client versions.

## Acceptance criteria

- A dated rehearsal record shows successful restore and rollback steps.
- Monitoring detects stopped scheduler/bot and queue-age or terminal failures.
- Runbook commands are accurate for the selected host and storage provider.

## Validation

Perform the rehearsal on disposable but representative host data; do not use
production guild data without an approved backup and maintenance window.

