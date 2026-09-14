# Task register

This directory is the source of truth for planned repository work. Feature
boundaries are recorded in [FEATURE_STATE.md](FEATURE_STATE.md); each actionable
item has its own file under `todo/`, `in-progress/`, or `complete/`.

## Status flow

`todo` → `in-progress` → `complete`

Only one agent or contributor may own a task at a time. A task document should
state its problem, scope, acceptance criteria, dependencies, and validation.
Keep it concise and update it when newly discovered work changes its scope.

## Starting a task

1. Ensure the worktree is clean or that unrelated work is safely committed.
2. Update your local `main`: `git fetch origin && git switch main && git pull --ff-only origin main`.
3. Create a branch from current `main`.
4. Move the selected task from `tasks/todo/` to `tasks/in-progress/` with `git mv`.
5. Commit and push that move before editing code. This is the ownership claim
   that prevents another agent from selecting the same task.

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

