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

