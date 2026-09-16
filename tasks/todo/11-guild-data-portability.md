# Guild data portability between OpenIQ instances

Priority: P1  
Owner: unassigned

## Problem

A guild needs a supported way to move its OpenIQ data to another OpenIQ
instance without directly copying a live database or relying on host-specific
backup files.

## Scope

- Provide an owner-authorised export of one guild's portable data from the web
  application.
- Define a versioned, documented export format and include only data required
  to recreate the guild's operational history and configuration.
- Provide an owner-authorised upload/import flow on a different OpenIQ
  instance, with validation, an explicit preview, and confirmation before it
  writes data.
- Define how imports handle conflicts, identity links, secrets, external
  integration credentials, and Discord server-specific identifiers safely.
- Make exports downloadable by the authorised owner and ensure they are not
  retained by the server after the response completes.

## Non-goals

- Moving a whole OpenIQ installation, its database, backups, or server-wide
  settings.
- Exporting credentials, session material, OAuth tokens, bot tokens, or
  instance secret keys.
- Automatically reconnecting a destination instance to Discord or other
  external services.

## Dependencies

- Owner role and guild-scoped access controls.
- Existing member and war export formats should be evaluated for reuse or a
  compatible migration path.

## Acceptance criteria

- An authorised owner can download a documented, versioned export for their
  guild and an unauthorised user cannot obtain it.
- A destination owner can upload the export, review its contents and warnings,
  and explicitly confirm a validated import.
- The imported guild preserves supported roster, event, war, attendance, and
  configuration records without exposing secrets or stale external identities.
- Invalid, tampered, incompatible, and conflicting imports fail without
  partial writes or data loss.
- The interface clearly identifies any information that needs manual
  reconfiguration after transfer.

## Validation

- Focused unit and integration tests for authorisation, export redaction,
  schema/version validation, dry-run preview, rollback on failure, and conflict
  handling.
- Browser coverage for the owner download/upload/confirm workflow.
- Run the relevant test suite on Linux and Windows.
