# Provide scheduled jobs with the Swarm SQLite runtime

Priority: P1  
Owner: unassigned

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
Run relevant automated regressions on Linux and Windows before completion.
