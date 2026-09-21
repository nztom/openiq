# Provide scheduled jobs with the Swarm SQLite runtime

Priority: P1  
Owner: Codex

## Problem

The Swarm example runs web, an optional bot, and backups, but no application
scheduler. Bot connection does not execute `tick`. The authorized live check
on 2026-09-17 confirmed runbot and backup_scheduler present, scheduler absent,
and readiness OK. Without an external scheduler, reminders, recurrence,
scheduled summaries/roster sync and queued delivery do not run automatically.

## Scope

Provide an explicit opt-in way to run the existing scheduler against the exact
web database on Swarm (reuse the small existing supervisor if appropriate).
Wire heartbeat, startup/shutdown, failure handling and example configuration.
Keep scheduling optional and explain what remains manual when disabled.
Non-goals: a general job framework or automatic production deployment.

## Dependencies

Coordinate with in-progress tasks 13 (deployment examples) and 15 (embedded
bot runtime); task 07 retains live Discord recovery acceptance.

## Acceptance criteria

- Enabled jobs use the same node-local database as web and bot.
- Exactly one scheduler runs and its failure is visible to readiness/operators.
- Disposable due jobs execute and survive a worker restart without duplication.
- Disabled configuration clearly describes manual tick/delivery requirements.

## Validation

Run focused supervision and scheduler tests, render deployment examples, and
exercise due jobs/restart in a disposable Swarm deployment. Do not send test
messages to a production Discord guild.
Run relevant automated regressions on Linux and a disposable Linux Swarm before
completion.

## Implementation progress

- Added `RUN_SCHEDULER=1` and a bounded `SCHEDULER_INTERVAL` to the web-container
  supervisor. Enabled schedulers share `/data`, automatically become readiness
  requirements, stop cleanly, and force a container restart after unexpected
  exit.
- Compose and Swarm examples keep the scheduler opt-in inside the single web
  replica. Deployment and runbook guidance explain the one-replica SQLite
  constraint and manual `tick` behavior when disabled.
- Linux validation on 2026-09-21 passed shell syntax, 11 scheduler/readiness/
  delivery/environment tests, `manage.py check`, `git diff --check`, Compose
  rendering, and Swarm-stack rendering.
- The skill-guided read-only live check found all four Pi nodes healthy, all
  services at desired replicas, and only `openiq_web` in the OpenIQ stack,
  confirming that the deployed stack has no application scheduler.
- Disposable Linux Swarm validation on 2026-09-21 built commit `680d4c5`, ran
  one web replica and one scheduler against an isolated node-local volume, and
  reported the scheduler healthy through `/readyz/`.
- An overdue disposable reminder became `previewed` with exactly one outbox
  row. Terminating the scheduler stopped the supervised web process, Swarm
  replaced the task, readiness recovered, and the persisted reminder still
  had exactly one outbox row. Discord delivery was disabled throughout.
