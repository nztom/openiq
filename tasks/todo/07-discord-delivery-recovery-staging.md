# Discord delivery, tickets, and restart recovery staging

Priority: P1  
Owner: unassigned  
Depends on: 03-discord-staging-acceptance

## Problem

Delivery, ticket, reminder, and reconciliation behavior has controlled-response
coverage but needs a staging-guild failure and restart exercise.

## Scope

- Exercise queued delivery, ticket transcript updates, reminders, retries,
  uncertain outcomes, operator reconciliation, and restarts.
- Verify that failure recovery does not create duplicate remote messages or
  channels.

## Acceptance criteria

- Restart and partial-failure recovery has an operator-approved path.
- Required bot permissions and manual reconciliation steps are documented.
- Any Discord-platform limitation is reflected in feature state and the runbook.

## Validation

Use dedicated staging credentials and explicitly enabled delivery; do not use a
production guild as the recovery test target.

