# Feature state

Last reviewed: 2026-09-14.

OpenIQ is a self-hosted, small-guild Django application. The local release gate
validates its offline workflows using disposable storage, synthetic OCR/packet
fixtures, controlled external-service responses, browser checks, and a 100%
Python coverage threshold. That is useful release evidence, not proof of a live
guild installation.

| Area | State | Boundary |
| --- | --- | --- |
| Core guild workflows | Locally validated | A real officer/member event and war still need acceptance. |
| Access, privacy, and settings | Locally validated after PR #4 reconciliation | Continue regression coverage as new response shapes are added. |
| Discord/OAuth/delivery | Implemented with controlled mocks | Staging credentials, permissions, restarts, and ambiguous remote outcomes need live validation. |
| BDO capture and OCR | Synthetic fixtures validated | Current-patch traffic, regional screenshots, and sustained capture are unverified. |
| Backup, restore, upgrade | Commands and Compose support implemented | Rehearse off-host backup, restore, and failed-upgrade recovery on the selected host. |
| PostgreSQL | Adapter and integration tests exist | Run them against the selected PostgreSQL version and matching client tools. |
| Deployment and operations | Runbook, readiness checks, and diagnostics implemented | Build/run the image and validate TLS, proxy, monitoring, alerts, shutdown, and capacity on the target Ubuntu host. |
| Accessibility | Automated keyboard/layout/axe coverage | A person using a screen reader must complete the acceptance workflow. |

Historical technical evidence remains in `docs/PR4_REVIEW.md`,
`docs/PR4_INTEGRATION.md`, `docs/PRODUCTION_AUDIT.md`, and the operator-facing
documents in `docs/`. New work must be tracked here, rather than adding another
parallel checklist to those reports.

