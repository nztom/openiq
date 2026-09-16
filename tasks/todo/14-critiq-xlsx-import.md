# Import Critiq XLSX exports

Priority: P1  
Owner: unassigned

## Problem

Guilds moving from Critiq need a supported way to import their authorised XLSX
exports into OpenIQ without manually re-entering roster and historical data.

## Scope

- Obtain representative, authorised and sanitised Critiq XLSX exports and
  document the supported export versions, worksheets, and columns.
- Provide an owner-authorised XLSX upload/import flow with schema validation,
  a field mapping preview, warnings, and explicit confirmation before writing.
- Import the supported roster and historical guild data while preserving the
  source-export provenance in the audit trail.
- Define deterministic matching and conflict handling for family names,
  duplicate rows, missing required values, unknown classes, dates, and records
  that already exist in the destination guild.
- Apply strict file-size, worksheet-count, cell-content, and archive-safety
  limits before parsing the spreadsheet.

## Non-goals

- Connecting to, scraping, or automating Critiq's live service.
- Importing passwords, OAuth tokens, Discord bot tokens, or other credentials.
- Silently merging ambiguous records or replacing existing guild data.
- Supporting arbitrary Excel workbooks not produced by the documented Critiq
  export flow.

## Dependencies

- Authorised sample exports and consent to retain only sanitised regression
  fixtures.
- Task 11, where shared import-preview, confirmation, and conflict-handling
  components may be reusable.

## Acceptance criteria

- An owner can upload a supported Critiq XLSX export, see exactly what will be
  created, updated, skipped, or rejected, and explicitly confirm the import.
- Unsupported, malformed, oversized, formula-bearing, encrypted, or unsafe XLSX
  files fail clearly without partial writes.
- Supported imports preserve the documented roster/history fields and create an
  audit record identifying the Critiq import and source version.
- Existing destination records are never overwritten without a clearly reviewed
  conflict decision.
- Operators can follow documented limitations and manual reconciliation steps.

## Validation

- Unit and integration coverage for supported schema versions, malformed ZIP/XLSX
  content, parser limits, authorisation, previews, conflict handling, rollback,
  and audit provenance.
- Browser coverage for owner upload, preview, confirmation, and rejection paths.
- Validate the import on Linux and Windows with sanitised representative exports.
