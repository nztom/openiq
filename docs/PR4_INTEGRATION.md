# PR #4 local integration — 2026-09-13

PR head `8b01428420c0887e4e0163abd88aebcc2fcec6cb` is combined with the previously
uncommitted delivery changes on local branch `reconcile/pr4-readiness`.

## Resolved conflicts

| Area | Resolution |
| --- | --- |
| Delivery | One queue using typed `Outbox` claims, retry times, errors, and explicit uncertain outcomes. Retained full-text attachments, added the PR's queued-state recheck, and fenced stale acknowledgements. |
| Scheduler | Uses the shared queue while preserving shutdown checks, heartbeat updates, and reminder completion. Invalid preview destinations are filtered before the batch limit. |
| Community | Retained ticket reopening and dedicated reminder destinations. Cancelling a reminder cancels unsent retries. Updating previews or ticket transcripts preserves in-flight and uncertain claims. |
| Models | Retained both the outbox fields and the PR's `RequestLimit` model. |
| Migrations | Preserved both existing `0002` names. `0003_merge_delivery_and_request_limits` joins the branches and imports legacy PR retry metadata; ambiguous sends require reconciliation. |

Automatic message recovery is available as an explicit, read-only
`reconcile_delivery --find` operation. It verifies the exact authenticated bot,
then verifies the selected message's author and channel. Uncertainty no longer
causes an automatic message-create retry. Manual ID verification and confirmed
absence remain available. See [the runbook](RUNBOOK.md).

The old implementations' tests were reconciled with this contract. Added checks
cover preview-queue starvation, stale selections, backoff/cancellation, stale
acknowledgements, foreign-bot messages, conflicting reconciliation, and real
migration upgrades from `0001` and either `0002` branch.

## Validation

The complete `scripts/release_gate.py` passed on Ubuntu/Python 3.14 after
integration: 230 tests, two PostgreSQL-only skips, 100% statement and branch
coverage, production checks, synthetic OCR/import/packet fixtures, JavaScript
syntax, Compose configuration, accessibility regressions, and the complete
browser war lifecycle. The migration regressions exercise fresh `0001` storage
and upgrades from either independent `0002` branch. Django reports no missing
model migrations; the combined graph has no conflicting leaves.

Reproduce with:

```sh
COVERAGE_FILE=/tmp/openiq-reconcile-coverage .venv/bin/python scripts/release_gate.py \
  --output /tmp/openiq-reconcile-release-report.json
.venv/bin/python manage.py makemigrations --check --dry-run
```

The local integration changes remain uncommitted on the branch based on the PR
head. Committed `main` remains at `3761c70`.

## Scope and remaining work

This integration addresses all six reproduced PR review findings:

- R1: successful member responses recursively omit private notes, including
  command aliases, while preserving officer responses and stored notes.
- R2: admin password attempts have an IP request budget. Recovery credentials
  are written to a private mode-600 file instead of container logs; failed
  credential publication rolls back account changes.
- R3: milestones, welcome selections and schedule source URLs are validated.
  A failed guild job no longer prevents other guilds or delivery from running;
  the scheduler still reports failure for monitoring.
- R4/R6: reconciliation verifies the authenticated bot and notifications retain
  full content, as described above.
- R5: external reads are prepared before acquiring the shared mutation
  transaction. Authorization, configuration and guild revision are rechecked
  before committing results. Welcome role HTTP calls also run outside the
  component transaction. War history records changed rows rather than scanning
  every war before and after unrelated actions. An independent-process SQLite
  regression verifies that another writer succeeds during mocked HTTP calls.

The candidate still needs deployment evidence: an image/runtime and proxy
rehearsal, off-host backup and fresh-host restore, failed-upgrade recovery,
monitoring/alerting, and live Discord staging acceptance. PostgreSQL integration
tests must run if that backend is selected. CI/security scanning, measured
capacity, bounded state payloads and deeper integrity checks remain broader
readiness work. The [PR review](PR4_REVIEW.md) preserves the original findings;
this document supersedes its local defect and integration status.

No running database was migrated, no services were deployed, and no Discord
messages were sent. The GitHub PR remains open. Original local edits were backed
up under `/tmp/openiq-before-pr4-GGBYx0` before integration.
