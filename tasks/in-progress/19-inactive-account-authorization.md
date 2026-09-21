# Enforce inactive-account denial across action transports

Priority: P1  
Owner: Codex

## Problem

`services.access` checks authentication and Access membership but not
`user.is_active`. Discord commands/components also create or retrieve users
without rejecting inactive accounts. An inactive existing user can retain
Discord role authorization and mutate guild data. A disposable reproduction
on 2026-09-17 set `is_active=False` and successfully created a reminder through
`execute`; capture ingestion already rejects inactive accounts explicitly.

## Scope

Apply a consistent inactive-account check at the shared authorization boundary
and Discord entry points, including autocomplete. Review OAuth callback
handling so disabled accounts cannot be admitted through that flow.
Non-goal: changing the Discord role-to-guild mapping.

## Dependencies

None.

## Acceptance criteria

- Inactive accounts cannot read private guild data or mutate through any transport.
- Discord does not re-grant access or create linked identities for a denied action.
- Active users and explicitly reactivated users retain expected behavior.

## Validation

Exercise disabled accounts through shared execute, slash commands, components,
autocomplete, OAuth and capture with controlled responses; assert no writes.
Run relevant automated regressions on Linux and Windows before completion.
