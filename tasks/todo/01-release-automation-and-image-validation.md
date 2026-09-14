# Release automation and image validation

Priority: P1  
Owner: unassigned

## Problem

The offline release gate is locally runnable, but there is no checked-in CI
workflow or clean-image validation evidence for the reconciled release.

## Scope

- Add a GitHub Actions workflow that runs the reproducible offline gate.
- Build the Docker image from a clean checkout and exercise its basic startup,
  health/readiness routes, persistent volume, and enabled Compose profiles.
- Add dependency and secret scanning appropriate to this public repository, with
  reviewed baselines rather than ignored failures.

## Acceptance criteria

- Pull requests run the gate and expose useful logs/artifacts on failure.
- A fresh image build and disposable Compose runtime pass documented checks.
- Scan findings have an owner and disposition; no credentials are committed.
- The runbook and feature state describe the resulting automated coverage.

## Validation

Run `python scripts/release_gate.py`, the CI workflow, and documented disposable
Docker/Compose smoke checks.

