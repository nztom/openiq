# Local release and image smoke validation

Priority: P1  
Owner: unassigned

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

