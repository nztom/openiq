# Discord staging acceptance

Priority: P1  
Owner: unassigned

## Problem

Discord features are covered with controlled responses but have not been run
against a staging guild.

## Scope

- Validate OAuth login and role revocation, bot installation/sync, commands,
  components, welcome roles, tickets, reminders, restarts, and permission
  failures.
- Exercise delivery retry and operator reconciliation without sending duplicate
  production messages.
- Record required Discord permissions and any product limitations discovered.

## Acceptance criteria

- The staging checklist passes for owner, officer, member, and denied roles.
- Restart and partial-failure behavior has an operator-approved recovery path.
- Docs accurately name required scopes, permissions, and manual steps.

## Validation

Use only a dedicated staging guild and explicitly enabled delivery credentials.

