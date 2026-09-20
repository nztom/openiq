# Task register

This directory is the source of truth for planned repository work. Feature
boundaries are recorded in [FEATURE_STATE.md](FEATURE_STATE.md); each actionable
item has its own file under `todo/`, `in-progress/`, or `complete/`.

## Status flow

`todo` → `in-progress` → `complete`

Only one agent or contributor may own a task at a time. A task document should
state its problem, scope, acceptance criteria, dependencies, and validation.
Keep it concise and update it when newly discovered work changes its scope.

## Planning and maintaining tasks

Before proposing new work, update from `main`, read `FEATURE_STATE.md`, and
search every task state for related work (for example,
`rg -n -i 'keyword' tasks`). Read possible matches before creating anything.

- Extend an existing task when the outcome, code area, and acceptance criteria
  are materially the same. Do not create a second task for a different slice of
  the same problem.
- Create a new `todo/` document only when its outcome can be independently
  claimed, implemented, tested, and completed. Split a broad effort into those
  independently deliverable slices.
- Every new task must state: priority, owner (`unassigned` initially), problem,
  scoped outcome, explicit non-goals where useful, dependencies, acceptance
  criteria, and validation. Windows runtime validation is required for desktop
  capture and other OS-facing behavior, not ordinary web/server changes. Link
  related task IDs instead of copying their text.
- Update a task when planning changes its scope, dependencies, or acceptance
  criteria. Do not edit an `in-progress/` task owned by someone else; add a
  separate coordination note or contact its owner instead.
- Commit and push task-register-only planning changes so future agents plan from
  the same current backlog. Update `FEATURE_STATE.md` when a task changes a
  documented feature boundary.

## Keep the workflow small

- Use one task branch and one PR per independently deliverable change. Batch
  related backlog discoveries into that PR; no separate audit backlog is needed.
- A new task can be planned and claimed in the same published planning commit
  before implementation. Existing tasks still use the move-and-push claim.
- Branch claims are not visible in `main` until merged. During overlap checks,
  inspect open PRs and their task documents as well as local task states. Open
  the task PR when publishing the claim so other contributors can find it.
- Run focused tests for the changed behavior and Django checks. Use browser,
  OCR, database and container checks when those paths change. Reserve the full
  offline release gate for release validation or changes that warrant it.
- Documentation-only changes need link/command review, not a runtime or the
  full coverage/browser gate. Web/server tasks need relevant Linux validation;
  OS-facing tasks need validation on each supported target platform.
- No CI service, branch protection, extra reviewer or approval ceremony is
  required. Put validation and any remaining limitations in the task and PR.

## Documentation

Keep `docs/` for maintained instructions and behavior reference. Put concise
reproduction steps and validation results in the relevant task; use the PR
body for change summaries. Do not add dated audit reports, PR-review narratives,
agent session logs or duplicate readiness/backlog checklists. Preserve useful
operating instructions in the appropriate guide and let Git retain history.

## Starting a task

1. Ensure the worktree is clean or that unrelated work is safely committed.
2. Update your local `main`: `git fetch origin && git switch main && git pull --ff-only origin main`.
3. Create a branch from current `main`.
4. Move the selected task from `tasks/todo/` to `tasks/in-progress/` with `git mv`.
5. Commit and push that move before editing code, then open its PR with the
   task ID in the title or description. Check other open claims before editing;
   a branch push alone does not reserve a task in `main`.

## Completing a task

1. Rebase or merge the latest `origin/main` as appropriate and resolve any
   task-ownership conflict deliberately.
2. Implement the scoped work and run the task's listed validation.
3. Update the task document with the completed outcome and evidence.
4. Move it to `tasks/complete/` with `git mv` **in the same commit as the code
   and tests**. Do not make a separate completion-only commit.
5. Push the branch and open or update its pull request.

If work is paused, leave the document in `in-progress/` with a short handoff
note rather than returning it to `todo/` silently. A maintainer may return it
to `todo/` once the ownership claim has been cleared.

## Cross-platform requirement

Keep application code and tests OS-agnostic. Avoid shell-specific commands,
hard-coded paths, Unix-only process behavior, permissions assumptions, and
platform-specific dependencies. Linux validation is sufficient for ordinary
web and server changes. Validate live desktop capture, local client,
installer/updater, and other explicitly OS-facing behavior on each supported
target platform; if a required platform exposes a defect, keep that task in
progress until it is fixed rather than documenting it away.
