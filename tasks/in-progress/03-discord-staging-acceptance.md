# Discord identity, bot, and command staging

Priority: P1  
Owner: nztom

## Problem

Discord features are covered with controlled responses but have not been run
against a staging guild.

## Scope

- Validate OAuth login and role revocation, bot installation/sync, commands,
  components, welcome roles, and permission failures.
- Record required Discord permissions and any product limitations discovered.

## Acceptance criteria

- The staging checklist passes for owner, officer, member, and denied roles.
- Docs accurately name required scopes, permissions, and manual steps.

## Validation

Use only a dedicated staging guild and explicitly enabled delivery credentials.

## Progress

- The Pi Swarm deployment is healthy at version `6e827933e3be`: web readiness,
  database, migrations, storage, and the embedded bot heartbeat pass, and the
  bot resumed its Discord gateway session.
- Read-only diagnostics pass for guild 1: the bot token and installation are
  valid, ticket-channel creation is allowed, and no registered commands are
  missing. Guild 1 (`turtle_power`) is the authorized development workspace.
  Guilds 2 (`Purge`) and 3 (`Hostile`) belong to an independent tester and are
  outside this task; do not inspect, alter, or use them for validation.
- Found and fixed `bot_diagnostics` ignoring `DISCORD_BOT_TOKEN_FILE` when run
  with `docker exec`; `guilds.test_bot_diagnostics` passes on Linux and covers
  Docker-secret file loading. `python manage.py check` also passes.
- Added the role, command, component, revocation, and permission-failure staging
  checklist to the runbook. The four-role interactive checks remain pending.
