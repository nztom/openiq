# Repository review and lightweight contributor workflow

Priority: P2  
Owner: Codex (repository review)

## Problem

The repository needs a current review of correctness, documentation, feature
boundaries, and contributor overhead.

## Scope

- Review application and operational paths and reproduce actionable defects.
- Record bugs and missing features in scoped tasks, reusing existing tasks.
- Correct stale current documentation and clarify a minimal contributor loop.
- Record review evidence and limitations without creating a parallel backlog.

## Non-goals

- Implementing the bugs or product features discovered by this review.
- Adding CI, branch protection, dependencies, or mandatory release checks.
- Taking over another contributor's in-progress task.

## Dependencies

- Current task register and feature state.

## Acceptance criteria

- Findings have concrete evidence and links to canonical tasks.
- Current documentation matches implemented behavior.
- Everyday checks are distinguished from optional full release validation.

## Validation

- Run applicable existing automated tests in disposable storage.
- Check changed Markdown links and Git whitespace.
- Documentation-only work needs no Windows runtime; any code change requires
  relevant Linux and Windows validation before completion.

## Outcome

Completed 2026-09-17. [Review evidence](../../docs/REVIEW_2026-09-17.md)
records four reproduced application defects, missing Swarm scheduling, and
coordination notes for existing tasks. Added todo tasks 18–22 and corrected
current README, database, deployment, feature-state and workflow guidance.
Historical READINESS no longer acts as a second backlog.

The existing suite passes on Ubuntu: 244 tests, 8 optional tests skipped. The
autocomplete sandbox timeout does not reproduce outside the sandbox. Authorized
read-only live checks confirmed healthy web/bot/backups and absent scheduling.
No application code changed, so Windows runtime validation is not required for
this documentation task; each new code task explicitly requires both platforms.

JavaScript syntax, both Compose configuration renders, 34 changed-document
local links and Git whitespace checks passed.

## Follow-up: remove documentation clutter

Reopened 2026-09-17 at the user's request. Remove superseded PR reviews, audit
reports and duplicate readiness/research inventories. Keep actionable findings
in existing tasks, preserve useful compatibility provenance in contracts, and
fix references in maintained documentation. Do not add another review report.
Validation: repository Markdown links, removed-document references and whitespace;
no application code changes or runtime tests are needed.
