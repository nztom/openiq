# Local release and image smoke validation

Priority: P1  
Owner: Codex

## Problem

The offline release gate is locally runnable, but the reconciled release has no
recorded clean-image and disposable Compose runtime validation.

## Scope

- Build the Docker image from a clean checkout and exercise its basic startup,
  health/readiness routes, persistent volume, and enabled Compose profiles.
- Record reproducible local commands and results in the runbook or task outcome.

## Acceptance criteria

- A fresh image build and disposable Compose runtime pass documented checks.
- The runbook describes the resulting local smoke checks and their limits.

## Validation

Run `python scripts/release_gate.py` and documented disposable Docker/Compose
smoke checks. This task does not add a CI, branch-protection, or PR-review gate.

## Outcome

Completed 2026-09-14 on Ubuntu Desktop:

- `.venv/bin/python scripts/release_gate.py` passed with the release report in
  `/tmp/openiq-release-report.json`.
- `docker build --pull --no-cache --tag openiq:local .` built successfully.
- A disposable `openiq-smoke-20260914` Compose project passed `/healthz/`,
  `/readyz/`, `diagnostics`, SQLite persistence across a web restart, and the
  `jobs` scheduler-profile startup. `docker compose ... config --quiet` passed
  with jobs, Discord, and backup profiles enabled.
- `docs/RUNBOOK.md` now records the reproducible local commands and their
  boundary: Discord staging, host TLS/proxy, backup directory/restore, and live
  service validation remain separate tasks.
