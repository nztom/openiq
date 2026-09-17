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
