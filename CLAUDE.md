# Repository workflow for Claude and other agents

Before taking implementation work, read [tasks/README.md](tasks/README.md) and
[tasks/FEATURE_STATE.md](tasks/FEATURE_STATE.md). Use that task register rather
than creating a competing TODO list.

Always update from `main` before task selection:

```bash
git fetch origin
git switch main
git pull --ff-only origin main
```

Create a branch, claim exactly one task by moving its file from `tasks/todo/` to
`tasks/in-progress/`, and commit **and push** that claim before editing code.
On completion, update the task evidence and move the file to `tasks/complete/`
in the **same commit** as the implementation and tests; push that commit. Leave
paused work in `tasks/in-progress/` with a handoff note.

For new or revised plans, follow the planning rules in `tasks/README.md`: search
all task states first, extend a matching task rather than duplicating it, and
make each new todo independently deliverable with scope, non-goals where useful,
dependencies, acceptance criteria, and validation. Commit and push planning
changes; do not edit another owner's in-progress task.

When changing behavior or adding code, add or update focused automated tests
where practical, and run the relevant tests before handoff. This is an
engineering expectation, not a protected-branch, CI, or pull-request gate.

All fixes and features must be OS-agnostic and run on both Linux and Windows.
Avoid shell-specific commands, hard-coded paths, Unix-only process behavior,
permissions assumptions, and platform-specific dependencies in application code
and tests. Validate code tasks on both operating systems before completion.
