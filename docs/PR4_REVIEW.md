# PR #4 review, reconciliation, and readiness reassessment

**Integration update (2026-09-13):** the conflicts described here have since been
resolved locally on `reconcile/pr4-readiness`; see [integration notes](PR4_INTEGRATION.md).
This document retains the review of the original PR head. It is not a claim that
all production findings have been fixed or that the GitHub PR has been merged.

Reviewed on 2026-09-12. **Recommendation: request changes before integration; substantially closer to a production candidate, but not launch-ready.** This is a local review, not a submitted GitHub review or merge.

[PR #4 — Complete locally verifiable guild readiness tasks and release gate](https://github.com/nztom/openiq/pull/4) changes 107 files, adding 3,474 lines and removing 208. Its branch name, `feat/scheduled-backups`, understates its scope. The reviewed head is `8b01428420c0887e4e0163abd88aebcc2fcec6cb`; the common ancestor is our current committed main, `3761c706685f08d1c1921e85b08186c797199294`. The PR head was rechecked after testing and had not changed. GitHub reports it mergeable against committed main, with no reported CI checks or reviews.

The original working tree, its uncommitted delivery work, and host database were preserved. Review and testing used `/tmp/openiq-pr4-review-EAz531`. This report reconciles the implementations and audit findings; it does not claim that application changes have been merged.

## Independent Ubuntu validation

Ran the PR's `scripts/release_gate.py` using the existing Ubuntu Python 3.14 environment, with its locked axe-core dependency installed in the disposable checkout. The script uses disposable application storage and mocked external services.

| Check | Observed result |
| --- | --- |
| Django/application/browser test suite | 218 tests in 20.158 seconds; passed, with 2 PostgreSQL-only tests skipped |
| Statement and branch coverage | Configured 100% gate passed |
| Django normal and production deployment checks | Passed |
| Command registry | Passed |
| Synthetic CSV/OCR/IKUSA/JSONL and packet checks | Passed |
| JavaScript syntax, all static JavaScript files | Passed |
| Compose configuration with optional profiles | Passed |
| Disposable migrations and demo fixtures | Passed |
| Complete browser war lifecycle | Passed |
| Automated accessibility/browser regressions | Included in the passing suite |

This independently confirms the offline gate on Ubuntu; it is stronger evidence than the PR's Windows-only report. It does not validate a fresh install of every Python dependency, a Docker image build/runtime, PostgreSQL, live external accounts, sustained load, or a target-host disaster recovery rehearsal. The existing environment ran the SQLite gate; the two added PostgreSQL dependencies were not required by that path.

## Review findings

### R1 — P1: Private officer notes still leak through allowed member mutations

**Inherited defect left unresolved by the readiness changes.** A linked member can POST a class update and receive `result.notes`, despite the dashboard state endpoint and privacy export hiding those notes. Reproduced against the PR with HTTP 200 and `[{"text":"officer-only note"}]` in the response.

Relevant code: `guilds/modules/roster.py:4–12`, `guilds/views.py` (`action`), `guilds/modules/core.py` (`public`), and the new `guilds/test_permissions_matrix.py`. The matrix checks denied actions and private state records but does not check private fields in successful mutation responses. Other member-returning handlers need the same review.

**Required change:** role-aware response serialization at the shared boundary, with HTTP and Discord regression tests for allowed class/Twitch/welcome mutations. The SEC-05 completion claim should remain qualified until these tests pass.

### R2 — P1: The new request limiter omits the production password-login endpoint

**New protection is incomplete.** `guilds/rate_limits.py:25–30` budgets `/login/` and Discord OAuth, but not `/admin/login/`. Production member login uses Discord; the enabled recovery administrator is the remaining password-login path.

Reproduced by calling `RequestBudgets` for a POST to `/admin/login/` while its budget function was mocked to deny every request: the request reached the downstream view and the budget function was never called. This proves missing middleware coverage, not successful authentication.

**Required change:** apply a dedicated admin-login budget and test CSRF-valid repeated failed logins. Do not rely on `/login/` protection to cover Django admin. The inherited recovery command still prints its generated superuser password directly to stdout; the new logging filter does not sanitize that output. Replace routine log delivery with a private operator retrieval mechanism before production.

### R3 — P1: Accepted settings can still stop the scheduler

**New validation closes the original `roles=[]` defect but leaves other supported settings unchecked.** `guilds/settings_validation.py:5–49` does not validate `milestones`. `{"config":{"milestones":null}}` was accepted by `execute(..., 'admin', 'settings', ...)`; the next `operations.tick` raised `TypeError`.

The scheduler's per-run catch prevents process exit, but `tick` processes guilds before dispatching queued messages. A bad guild configuration can abort the pass, delay other guilds, and stop outbox delivery on every retry. Welcome role selections also lack a complete nested schema.

**Required change:** validate all accepted configuration fields, including milestone arrays and welcome selections; isolate per-guild scheduler failures; test that one invalid guild cannot prevent unrelated delivery. Keep A04 partially open.

### R4 — P2: Recovery can adopt a message from the wrong bot

**Introduced by automatic delivery reconciliation.** `guilds/delivery.py:65–79` matches a predictable footer and `author.bot`, rather than the authenticated bot's user ID. A different bot or bot-like webhook can supply that footer. Reproduced with a mocked foreign-bot message: the PR persisted its ID in the `delivery` record and then attempted to PATCH it, receiving 403. Subsequent retries use the incorrect stored ID.

**Required change:** verify exact bot author identity, channel, and uniqueness before persisting a recovered message. Retain explicit uncertain/manual reconciliation when verification fails. Our local `reconcile_delivery` command already verifies `/users/@me`; preserve that safety property when combining implementations. This finding does not imply that Discord permits editing another bot's message.

### R5 — P1: Slow integration calls still block SQLite writers

**Inherited issue, with additional work inside the transaction.** `guilds/services.py:13–34` holds a write transaction throughout dispatch, including external HTTP calls. The optional LLM request may take 45 seconds, exceeding the configured 20-second SQLite lock wait. The PR also loads all wars before and after many actions to create correction history, including commands that do not edit wars.

**Required change:** perform external I/O outside write transactions and revalidate before committing. Record targeted war changes rather than scanning the entire history for every applicable action. Validate independent processes with slow adapters against file-backed SQLite. A green single-process functional suite does not establish this behavior under contention.

### R6 — P2: Incoming delivery discards long notification content

**Inherited from committed main, but a regression relative to our local work.** `guilds/delivery.py:60` uses `item.text[:2000]`. A 2,500-character notification was sent as 2,000 characters and treated as successful. Large signup cards and summaries can silently lose content. The local implementation instead supports bounded attachments and counts UTF-16 units.

**Required change:** preserve full-content attachment handling while integrating the PR. Add tests for long ASCII and non-BMP Unicode content. Do not discard the local fix when resolving delivery conflicts.

## Reconciliation with the current working tree

Three-way comparisons using committed main as the ancestor produced a conflict region in each of these files:

| File | Our uncommitted implementation | PR implementation | Integration decision |
| --- | --- | --- | --- |
| `guilds/delivery.py` | Typed outbox retry/lease fields, explicit `uncertain` and terminal states, full-text attachments, operator reconciliation | JSON `delivery_retry`/`delivery_pending` records, automatic marker lookup, `queued=True` stale-item guard | Implement one state machine. Preserve explicit uncertainty, exact-author verification and full content; retain the PR's queued-state recheck and content/component race checks. |
| `guilds/management/commands/tick.py` | Calls `send_due()` | Own delivery loop, stop-event checks, scheduler heartbeat, reminder sent-state updates | Route one scheduler through the selected queue implementation; preserve stop/heartbeat/reminder behavior. |
| `guilds/models.py` | Adds four fields to `Outbox` | Adds `RequestLimit` | Both model additions are compatible, but require a reconciled migration graph. |
| `guilds/modules/community.py` | Preserves `sending`/`uncertain` and resets retries on content changes | Cancels queued reminders and adds ticket reopening | Preserve both domain behaviors while ensuring all producers obey the selected delivery state machine. |

The interfaces are not interchangeable: the PR scheduler calls `deliver(..., queued=True)`, while our local `deliver` does not accept that keyword. Choosing our delivery file and the PR scheduler would fail at runtime. Conversely, choosing the PR delivery file would abandon the local explicit-outcome and attachment behavior.

**Migration conflict reproduced:** both `0002_requestlimit` and our `0002_outbox_attempts_outbox_last_error_outbox_lease_until_and_more` depend on `0001_initial`. Loading both into Django produced two conflicting leaf migrations. Keep both independent operations and add a merge migration if both names must be preserved; do not rename an already-applied migration. Verify fresh install and upgrades from each existing migration state.

The local queue also has the previously reproduced 50-preview starvation bug; retaining local code unchanged is not a solution. The PR no longer uses that exact query, but counts invalid destinations as delivery attempts and retries them indefinitely. Test mixed valid/preview/failed queues and per-guild fairness in the reconciled implementation.

Recommended integration basis: use the PR for the broad readiness work, deliberately combine the four overlapping files, preserve and adapt the local reconciliation command and queue tests, resolve the migration graph, fix R1–R6, and run the gate against that combined result. The passing PR gate is not evidence that a combined implementation passes.

## Reassessment of the original audit

These dispositions describe the reviewed PR if integrated; committed main and the current local application files have not acquired these fixes.

| Original finding | Disposition after reviewing PR #4 |
| --- | --- |
| A01 — Officer-note disclosure | **Open.** Reproduced on the PR; R1. |
| A02 — HTTPS health redirect | **Specific defect fixed.** `/healthz/` now returns 200 with HTTPS enabled. Separate readiness is added. Production host allowlists still need to permit the actual internal probe, and Compose still uses liveness/offline bot construction rather than full readiness. |
| A03 — Queue starvation | **Different implementation; integration still open.** The old 50-item query is gone on the PR, but the local conflict and mixed-queue fairness must be resolved. |
| A04 — Invalid configuration | **Partly fixed.** Role objects, IDs, schedules, retention and several other fields are validated. Milestones can still break tick; R3. |
| A05 — SQLite contention | **Open.** Long transactions remain; correction-history scans add work; R5. |
| A06 — OCR resource limits | **Substantially addressed.** Streaming aggregate limit, file count, format/dimension verification, and a total OCR processing budget are implemented and tested. Target-host concurrency and reverse-proxy limits remain deployment checks. |
| A07 — Production defaults/secrets | **Partly fixed.** Demo defaults, startup validation, HSTS, session lifetime, adapter wiring, and log redaction improve. Recovery passwords still go to stdout, and admin login escapes rate limiting; R2. |
| A08 — Backup/restore/upgrade tooling | **Implementation gap substantially closed.** Scheduled bind-mounted backups, checked SQLite restore, PostgreSQL adapters, preflight and runbooks are present. Off-host copies and a real host restore/upgrade rehearsal remain outstanding. |
| A09 — Delivery/runtime observability | **Partly fixed.** Ticket recovery/reopen, role hierarchy/replacement, diagnostics, heartbeats and readiness exist. R4/R6, terminal/uncertain outcome handling, alerting and live verification remain. |
| A10 — Red release gate | **Fixed on the standalone PR.** Ubuntu offline gate passes, including 218 tests and 100% coverage. The combined local+PR result is untested; checked-in CI, image/runtime validation and security scanning remain absent. |
| A11 — Growth/dashboard cost | **Partly fixed.** Retention and cleanup tools exist; unrelated guild names are no longer exposed in the state directory. Unbounded state payloads, full scans and measured capacity remain open. |
| A12 — Governance/domain integrity | **Partly fixed.** Scoped exports, member privacy controls, maintenance and war correction history are implemented. Payload versioning, deeper integrity/repair checks and real retention/removal rehearsals remain. |
| A13 — Empty installation/live integrations | **Local UX substantially advanced and verified.** Onboarding, settings, empty states and automated accessibility checks pass. Live Discord, current BDO data where enabled, human accessibility checks and guild acceptance remain. |

PostgreSQL is no longer just a scaffold. Its two real integration tests were reported as passing by the contributor but were skipped in this Ubuntu SQLite review. The PR correctly documents that the default image includes PostgreSQL 15 client tools and newer servers need compatible tools. This constraint is supported by [Debian's Bookworm package](https://packages.debian.org/bookworm/postgresql-client) and [PostgreSQL's pg_dump compatibility documentation](https://www.postgresql.org/docs/17/app-pgdump.html); it should be exercised in the selected deployment, not counted as locally verified here.

## Remaining launch sequence

1. Resolve the queue/interface/migration conflicts and R1–R6; extend regression coverage beyond denial checks to successful-response privacy and failure recovery.
2. Rerun the complete release gate on the combined code; test both upgrade migration paths and a fresh database. Keep the uncommitted work until its behavior has been accounted for.
3. Build and run the resulting image on Ubuntu with disposable volumes, the actual proxy/host contract, enabled process profiles, graceful shutdown, worker failure and queue recovery.
4. Rehearse scheduled off-host backup, restore to a fresh installation, failed upgrade recovery, monitoring and alerts. Run the PostgreSQL gate with matching clients if selecting that backend.
5. Complete a Discord staging event/war, live permission and restart failures, and human acceptance. Verify current BDO capture only if it is part of the launch scope.

The revised assessment is **a substantially more complete candidate with a reproducible offline gate**, rather than a prototype missing most operating tools. The remaining blockers are concrete correctness defects, integration work, and production rehearsals. Checking most readiness boxes does not supersede the reproduced failures above.

Temporary evidence for this session: `/tmp/openiq-pr4-release-report.json`, `/tmp/openiq-pr4-release-gate.log`, `/tmp/openiq-pr4-probes.py`, and `/tmp/openiq-pr4-reconciliation/`. No remote review, message, merge, deployment, or live Discord action was performed.
