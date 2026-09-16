# Run the Discord bot in the web container

Priority: P1  
Owner: Codex

## Problem

In Swarm, a separate bot service can be scheduled away from the web service and
therefore use a different node-local SQLite volume. The bot must share the web
service's exact database and signing-key context.

## Scope

- Add an explicit opt-in to run the Discord bot as a supervised child of the
  web-container entrypoint.
- Ensure the web process and embedded bot share one data directory and are
  stopped cleanly together, including the existing final backup behaviour.
- Fail and restart the container clearly if an enabled bot exits unexpectedly.
- Replace the separate Compose/Swarm bot-service guidance with the embedded
  runtime configuration and update deployment examples.

## Non-goals

- Running more than one Discord bot process per OpenIQ guild.
- Changing Discord command semantics, permissions, or bot-token storage.
- Adding a general-purpose multi-process supervisor.

## Dependencies

- A valid `DISCORD_BOT_TOKEN` supplied through a secret/file environment
  variable and explicit Discord delivery enablement.

## Acceptance criteria

- With the opt-in disabled, web startup remains unchanged and no bot connects.
- With the opt-in enabled, the bot starts after setup, shares the web data
  directory, and records a readiness heartbeat.
- Missing bot credentials or unexpected bot exit fail safely rather than
  leaving the web service silently degraded.
- Container shutdown stops the bot and preserves the final-backup behaviour.
- Compose and Swarm examples configure one web service, not a separately
  schedulable bot service.

## Validation

- Focused entrypoint and environment-validation tests for disabled, enabled,
  missing-credential, bot-exit, and graceful-shutdown paths.
- Compose and Swarm configuration validation.
- Run relevant tests on Linux and Windows; validate container behaviour on the
  target Linux Swarm host.
