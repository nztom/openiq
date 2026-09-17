# Agent instructions

Read [tasks/README.md](tasks/README.md) and [tasks/FEATURE_STATE.md](tasks/FEATURE_STATE.md)
before planning repository work. They are the canonical task register and
feature-boundary record. Keep `docs/` for maintained guides and reference; put
review findings and validation evidence in tasks and PRs, not separate reports.

Task workflow:

1. Start from current `main`: fetch, switch to `main`, and run
   `git pull --ff-only origin main` before choosing a task.
2. Before creating or selecting work, read the task-planning rules in
   `tasks/README.md`, search all task states for overlapping work, and update an
   existing task instead of creating a duplicate where appropriate.
3. Claim one `tasks/todo/` document by moving it to `tasks/in-progress/`, then
   commit and push that move before changing code.
4. Keep the task document current while implementing it. New planned work goes
   in a scoped `tasks/todo/` document and its planning change is committed and
   pushed so other agents see it.
5. When finished, move the document to `tasks/complete/` in the same commit as
   its code and tests, then push the branch.

Do not pick a task already in `tasks/in-progress/`. If work pauses, add a
handoff note there; do not silently move it back.

When changing behavior or adding code, add or update focused automated tests
where practical, and run the relevant tests before handing off. Tests are an
engineering expectation, not a protected-branch, CI, or pull-request gate.

All fixes and features must be OS-agnostic and run on both Linux and Windows.
Avoid shell-specific commands, hard-coded paths, Unix-only process behavior,
permissions assumptions, and platform-specific dependencies in application code
and tests. Validate code tasks on both operating systems before completing them.
