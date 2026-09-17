# Feature state

Last reviewed: 2026-09-17.

OpenIQ is a self-hosted, small-guild Django application. The local release gate
validates its offline workflows using disposable storage, synthetic OCR/packet
fixtures, controlled external-service responses, browser checks, and a 100%
Python coverage threshold. That is useful release evidence, not proof of a live
guild installation.

| Area | State | Boundary |
| --- | --- | --- |
| Core guild workflows | Existing regression suite passes; review found validation and response gaps | Tasks 18, 20 and 21 track reproduced defects; a real officer/member event and war still need acceptance. |
| Access, privacy, and settings | Regression-covered with an inactive-account gap | Task 19 tracks shared-service/Discord inactive-account enforcement. |
| Discord/OAuth/delivery | Bot connected and global commands synced on the Pi Swarm; workflow behavior remains mock-validated | Staging permissions, command use, restarts, and ambiguous remote outcomes need live validation. |
| BDO capture and OCR | Synthetic fixtures validated | Current-patch traffic, regional screenshots, and sustained capture are unverified. |
| Backup, restore, upgrade | Commands and Compose support implemented | Rehearse off-host backup, restore, and failed-upgrade recovery on the selected host. |
| PostgreSQL | Adapter and integration tests exist | Run them against the selected PostgreSQL version and matching client tools. |
| Deployment and operations | Pi Swarm deployment active; public proxy routing, backups, and embedded bot observed | Restore/failed-upgrade rehearsal, monitoring/alerts, capacity, and guild-facing acceptance remain unverified. |
| Scheduled jobs on Swarm | Runtime missing from compact examples and observed deployment | Task 22 adds an opt-in scheduler sharing web storage; healthy web/bot does not imply automatic delivery. |
| Portability and Critiq migration | Not implemented as user-facing import/export workflows | Tasks 11 and 14 cover instance transfer and Critiq XLSX import. |
| Accessibility | Automated keyboard/layout/axe coverage | A person using a screen reader must complete the acceptance workflow. |

Use the operator guides in `docs/` for setup and maintenance. Reproduction steps,
validation evidence and follow-up work belong in the task register. Git and PR
history retain earlier reviews; they are not maintained product documentation.
