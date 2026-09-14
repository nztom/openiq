# Agent instructions

Read [tasks/README.md](tasks/README.md) and [tasks/FEATURE_STATE.md](tasks/FEATURE_STATE.md)
before planning repository work. They are the canonical task register and
feature-boundary record; historical audit reports in `docs/` are evidence, not
an alternative backlog.

Task workflow:

1. Start from current `main`: fetch, switch to `main`, and run
   `git pull --ff-only origin main` before choosing a task.
2. Claim one `tasks/todo/` document by moving it to `tasks/in-progress/`, then
   commit and push that move before changing code.
3. Keep the task document current while implementing it.
4. When finished, move the document to `tasks/complete/` in the same commit as
   its code and tests, then push the branch.

Do not pick a task already in `tasks/in-progress/`. If work pauses, add a
handoff note there; do not silently move it back.

