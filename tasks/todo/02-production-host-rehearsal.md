# Ubuntu host runtime and network rehearsal

Priority: P1  
Owner: unassigned  
Depends on: 01-local-release-and-image-smoke

## Problem

Operational commands exist, but deployment assumptions have not been verified
on the Ubuntu host that will run OpenIQ.

## Scope

- Validate TLS termination, DNS, firewall, host allowlists, volumes, process
  profiles, graceful shutdown, readiness, and operator diagnostics.
- Document the selected host's configuration and any deliberate deviations from
  the runbook.

## Acceptance criteria

- Runbook commands are accurate for the selected host and storage provider.
- Start, restart, shutdown, readiness, and basic failure diagnostics work on the
  selected Ubuntu host.

## Validation

Perform the rehearsal on disposable but representative host data; do not use
production guild data without an approved backup and maintenance window.
