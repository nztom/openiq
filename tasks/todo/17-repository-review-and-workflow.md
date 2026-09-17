# Repository review and lightweight contributor workflow

Priority: P2  
Owner: unassigned

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
