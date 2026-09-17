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

Initial review completed 2026-09-17 in [PR #8](https://github.com/nztom/openiq/pull/8).
Four reproduced application defects and missing Swarm scheduling are recorded
in todo tasks 18–22. Corrected
current README, database, deployment, feature-state and workflow guidance.
The duplicate readiness checklist has since been removed.

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

## Retained review evidence and coordination

- Review base: `1c2f50cb593ef9aaf1682c6b318860b256b7ef92`. New bugs were
  reproduced in temporary SQLite storage; their payloads/results remain in
  tasks 18–21. The 244-test Ubuntu run skipped optional browser/PostgreSQL
  tests; Windows, the full coverage gate and live mutations were not exercised.
- Read-only live checks on 2026-09-17 returned 200 for HTTPS login, liveness and
  readiness. Swarm reported web 1/1, version `6e827933e3be`, bot and backup
  workers present, scheduler absent (task 22). The deployed image differed from
  reviewed main; these checks did not establish restore or guild acceptance.
- Task 15 coordination: root Compose still exposes the legacy bot profile and
  forwards sync-mode variables only there, not to web. Enabling both runtimes
  duplicates bots. Integration status still recommends removed bot/backup
  profiles. Coordinate example changes with task 13; their active ownership
  remains unchanged.
- Tasks 06/13 coordination: live service history had multiple image digests
  under one commit-style tag. Record the actual digest during rollback
  rehearsal; a successful backup heartbeat does not prove restore works.
- Task 16's historical autocomplete timeout was sandbox-specific: the isolated
  check passed outside it in 0.010 seconds, as did the full suite.

## Cleanup outcome

Removed six obsolete reports/inventories, including the report added by this
review. Retained compatibility provenance in the application contracts and
updated the runbook, README and feature-state links. Future review evidence
belongs in task records and PRs. Earlier narratives remain in Git history.
Documentation-only follow-up; application code and running services are unchanged.

Completed follow-up validation: all 32 repository-local Markdown links resolve,
no Markdown references remain to removed files, and `git diff --check` passes.
