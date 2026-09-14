# Ubuntu host runtime and network rehearsal

Priority: P1
Owner: Codex
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

## Outcome

Completed 2026-09-14 on the selected Ubuntu Desktop host (`pc.linux`) using
the disposable `openiq-rehearsal` Compose project and generated volume:

- Production-mode web validation, migrations, diagnostics, persistent storage,
  the scheduler profile, and graceful web stop/start passed. Readiness with
  `REQUIRED_PROCESSES=scheduler` passed before and after restart.
- A temporary Caddy proxy served `https://localhost:19443`; HTTPS `/healthz/`
  and `/readyz/` returned 200 with HSTS. Both the proxy and application ports
  were bound only to `127.0.0.1`.
- The host's DNS validation is `localhost`; UFW is inactive. This is a
  deliberate local-only configuration, not a public DNS/firewall rehearsal.
  Public exposure, monitoring/alerts, capacity, and guild-facing TLS remain
  outside this selected-host scope.
- Docker's built-in health probe previously failed with a strict
  `ALLOWED_HOSTS=localhost` because it sent `Host: 127.0.0.1`. The image now
  uses the documented `localhost` internal host header.
- `.venv/bin/python scripts/release_gate.py` passed; the report is at
  `/tmp/openiq-release-report-host-rehearsal.json`.
