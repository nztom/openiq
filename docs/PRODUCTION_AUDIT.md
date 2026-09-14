# Production readiness audit — 2026-09-12

**PR reassessment:** [PR #4 review and reconciliation](PR4_REVIEW.md) evaluates incoming commit `8b01428420c0887e4e0163abd88aebcc2fcec6cb`. Its complete offline gate passes on Ubuntu and addresses substantial portions of this audit, but unresolved defects and local integration conflicts remain. The findings below describe the original working-tree snapshot, not the incoming PR. Use the reassessment's A01–A13 table for current disposition.

**Verdict: not ready for production use by a real guild.** The repository has a substantial working feature set and useful tests, but reproducible privacy, configuration, queue, and deployment defects remain. Prioritize reliable operation and permission boundaries before adding more features.

Scope: working tree at `3761c70`, including the existing uncommitted delivery queue implementation, migration, reconciliation command, and tests. Target: the one-host, small trusted guild deployment described in `READINESS.md`. This audit did not modify application code, migrate the host database, deploy containers, or send Discord messages. Findings marked “reproduced” used an isolated in-memory database. Other findings are code review conclusions; load and real-service behavior require the launch rehearsals below.

## Verification results

| Check | Result |
| --- | --- |
| Full Django suite, under coverage | 148 tests in 12.662 seconds; 2 failures; 3 opt-in browser tests skipped |
| Separate opt-in browser regressions | All 3 passed in 3.168 seconds |
| Statement/branch coverage gate | Report rounds to 99%; fails the configured 100% gate (2,162 statements, 1 missing; 980 branches, 2 partial) |
| Django ordinary system checks | Passed |
| `DEBUG=0 HTTPS=1 manage.py check --deploy` | HSTS warning `security.W004`; production settings still need host-specific verification |
| `makemigrations --check --dry-run` | No missing model migrations in the working tree |
| `pip check` | No broken installed dependency requirements; this is not a vulnerability scan |
| `runbot --check` | 58 commands constructed offline |
| Synthetic OCR and packet verification | Both passed; OCR used real Tesseract |
| JavaScript syntax / Compose configuration | Both passed |

The initial sandbox suite stalled and was stopped after a complete run outside the sandbox. Scapy's interface discovery was also denied in the sandbox; synthetic packet verification passed outside it. These restrictions are not host defects. Coverage output was stored separately under `/tmp`, preserving the existing `.coverage` file.

The failing tests are:

- `guilds.test_delivery_queue.DeliveryQueueTests.test_backoff_terminal_failures_and_expired_leases`, line 45: expected one failure, got zero. Its loop resets status and attempts but leaves the future `retry_at`, so the next case is not due.
- `guilds.test_workflows.WorkflowTests.test_delivery_send_update_and_failure_preserve_state`, line 128: expects `preview`, but the updated implementation persists `retry`.

Both need reconciliation with the intended state machine. These failures alone do not establish that retry behavior is incorrect. The independently reproduced starvation defect below does.

## P1 — Resolve before a guild depends on the service

### A01. Member mutation responses disclose officer notes — reproduced

Evidence: `guilds/modules/roster.py:4–12`, `guilds/modules/integrations.py` (`twitch_link`), `guilds/modules/operations.py` (`welcome_role`), `guilds/modules/core.py` (`public`), and `guilds/views.py:28,42`.

The state endpoint deliberately strips member notes for the member role. A member's allowed class update returns the complete member payload, including those same notes. An isolated authenticated POST to `/api/<guild>/roster/class/` returned HTTP 200 with `result.notes = [{"text": "officer-only note"}]`. Other handlers returning the same member record need the same review, including Discord responses.

**Required:** centralize role-aware serialization and apply it to every response path. Add HTTP and Discord tests that assert private fields are absent after allowed mutations, not just that forbidden actions fail. Map to SEC-05.

### A02. HTTPS configuration breaks container health and dependent startup — reproduced redirect

Evidence: `Dockerfile:29–32`, `config/settings.py:36–42`, and Compose `depends_on: service_healthy`.

With HTTPS enabled, the current local health request returns `301 https://127.0.0.1:8000/healthz/`. The health probe follows redirects, but Gunicorn on port 8000 serves plain HTTP. Therefore the documented TLS deployment configuration makes the container health check fail; bot and scheduler startup depend on that health check. Omitting loopback from a production-only host allowlist introduces a separate probe failure.

**Required:** define an internal health-probe contract compatible with TLS termination and host validation. Test a fresh Compose deployment with the actual proxy settings and both optional services. Map to SEC-01, OPS-05, LIVE-03.

### A03. Preview-only notifications can permanently starve delivery — reproduced

Evidence: `guilds/delivery.py:74–83` in the uncommitted implementation.

`send_due()` selects the oldest 50 items before skipping nonnumeric channels. With 50 older `channel='preview'` rows and one later valid channel, repeated passes select only undeliverable rows. The isolated probe returned `{'sent': 0, 'failed': 0}` and made zero delivery calls. Preview rows are a normal output of several workflows, so this does not require malformed data.

**Required:** separate drafts from deliverable work, or filter eligible destinations before applying the batch limit. Test mixed queues and fairness across guilds. Map to BOT-09.

### A04. Settings accept values that break authorization and scheduling — reproduced

Evidence: `guilds/modules/adminops.py:9–14`, `guilds/discord_auth.py:32–43,52–63`, and `guilds/modules/operations.py`.

The settings action validates only the outer object and section names. It accepts `{"config":{"roles":[]}}`; the role resolver subsequently raises `AttributeError` for a non-owner because it expects a mapping. Similar unchecked nested values affect channels, schedules, and welcome roles. OAuth synchronization visits all configured guilds relevant to the user, so one broken configuration can disrupt the user's login/refresh across their guilds. This is an owner-triggered configuration defect, not unauthenticated privilege escalation.

**Required:** typed nested validation, canonical IDs and role names, bounds and timezone validation, atomic rejection, and a supported repair path. Apply identical validation to browser and Discord settings. Map to OPS-01 and UX-01; this backend validation must not wait for new forms.

### A05. External I/O runs while holding SQLite's writer lock

Evidence: `guilds/services.py:13–22`, `config/database.py` (`transaction_mode: IMMEDIATE`, 20-second timeout), `guilds/modules/ai.py` (45-second HTTP timeout), `guilds/modules/integrations.py`, and scheduled roster synchronization.

Every dispatched action enters a write transaction before calling the handler, including read-oriented Discord commands and external integrations. A slow optional LLM call can hold the database-wide writer lock longer than other writers' timeout. Even a member can invoke the summary action. Independent guilds, scheduler activity, and session writes share this database.

**Required:** move remote calls outside write transactions, keep state changes short, revalidate authority/state before committing, and provide controlled contention errors. Test real concurrent processes against a file-backed database with slow/failing adapters. PostgreSQL would reduce cross-guild contention but does not by itself remove long transactions. Map to OPS-06 and DB-02.

### A06. Upload limits apply too late and do not bound total OCR work

Evidence: `guilds/views.py:48–54`, `guilds/modules/integrations.py` (`ocr`), and `config/settings.py:45`.

There are useful existing protections: 10 images, 10 MB per image, 20 megapixels, and a 30-second Tesseract timeout. However, each file is read completely before its byte limit is checked. Django can spool oversized uploads before the view executes. The 12 MB `DATA_UPLOAD_MAX_MEMORY_SIZE` setting excludes multipart file data, so it does not impose the intended aggregate file limit. Ten sequential OCR operations can occupy a request handler for roughly five minutes. No application rate limiting or proxy upload contract is supplied. See [Django's upload setting definition](https://docs.djangoproject.com/en/5.2/ref/settings/#data-upload-max-memory-size).

**Required:** enforce total request/file limits at ingestion, check size before reading, constrain accepted formats and processing budget, and limit OCR concurrency. Add rate controls for OCR, admin login, OAuth, recovery, and expensive mutations. Map to SEC-02 and SEC-04.

### A07. Default operational configuration is unsuitable for production

Evidence: `compose.yaml`, `.env.example`, `config/settings.py`, and `guilds/management/commands/bootstrap_admin.py`.

Compose seeds demo accounts by default and starts without requiring OAuth configuration. Normal local login is disabled, which reduces exposure, but demo data and known-password accounts still should not exist in a real installation. The enabled recovery administrator prints a full superuser credential into logs on every web restart. This makes log access equivalent to possession of an application administrator credential. TLS is opt-in, HSTS is not configurable, and optional Twitch/Ollama variables are not forwarded through Compose. A `.env` value alone does not inject those variables into a container.

**Required:** a production environment contract with demo data disabled; early validation of required credentials, hosts and proxy settings; private operator retrieval of recovery credentials; explicit secret rotation; and complete optional-adapter wiring. Enforce deployment checks against the actual environment. See [Django's deployment checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/). Map to OPS-01, SEC-01, SEC-03.

### A08. Backup exists, but recoverability and upgrades are unproven

Evidence: `guilds/management/commands/backup.py`, `scripts/container-entrypoint.sh`, Compose, and OPS-03/04/07 in `READINESS.md`.

Online SQLite snapshots, restrictive permissions, signing-key inclusion, checksums, and retention are already implemented and tested. There is no supported restore command, scheduled off-host copy, restore rehearsal, or documented migration rollback sequence. Container startup automatically migrates before serving traffic. A snapshot on the same volume does not survive losing that volume.

**Required:** define acceptable data loss and downtime; automate private off-host backups; validate and restore into a fresh volume; rehearse an upgrade and failed upgrade with schema-compatible rollback. Keep external credentials recoverable separately. Map to OPS-03, OPS-04, OPS-07 and LIVE-03.

### A09. Delivery lifecycle and runtime health are not a dependable operating contract

Evidence: `guilds/delivery.py`, `guilds/discord_tickets.py`, `guilds/discord_welcome.py`, `guilds/management/commands/runbot.py`, and Compose health checks.

The in-progress queue usefully introduces claims, retries, uncertain outcomes, and reconciliation. It still needs independent-worker and crash tests. The claim query permits previously sent/failed items, so stale worker selections can cause redundant delivery attempts. Ticket creation lacks an equivalent durable claim and may duplicate channels after remote success/local failure; transcript updates overwrite outbox status directly. Welcome role requests rely on Discord to reject hierarchy/permission problems. The bot health check starts a separate `runbot --check`, which only constructs commands; it cannot detect a disconnected or stalled live bot. Scheduler health is disabled. Queue failures are mainly counters and rows without operator alerts.

**Required:** complete BOT-07–10, add heartbeats and queue-age/error alerts, and test connection loss, 429, deleted messages, permission revocation, abrupt termination, concurrent workers, and reconciliation. Define a realistic delivery guarantee: Discord nonce deduplication covers only a recent time window, not indefinite exactly-once delivery. See [Discord's message API](https://docs.discord.com/developers/resources/message#create-message).

### A10. The release gate is red and is not automated in the repository

Evidence: test results above, `.coveragerc`, README verification section, and absence of checked-in CI workflows.

The README's 119-test/100%-coverage and 53-command figures are stale. Python coverage can be high while response privacy and queue fairness remain incorrect. Three browser regressions pass, but this audit did not run the separate full dashboard lifecycle script against a container.

**Required:** resolve the two failures, satisfy the chosen coverage policy, and automate fresh dependency installation, migrations, production checks, unit/permission/concurrency tests, browser lifecycle, OCR/packet fixtures, JavaScript syntax, Compose validation, and an image build/smoke test. Add dependency and image vulnerability scans plus a secret scan; `pip check` establishes none of these. Record immutable release/image identifiers and align documentation. Map to QA-01 and DOC-02.

## P2 — Complete before broader adoption, or explicitly constrain the pilot

### A11. Bound data growth and dashboard cost

`guilds/views.py:20–35` returns nearly every record and recomputes multiple analytics views per state request; live sessions include raw events. Public recaps scan all session records in Python. Audit, outbox, session, capture, and history retention are not operationalized. The state response also reveals all local guild names/IDs, including unrelated guilds; decide whether that is an intentional discovery feature.

Define supported guild/history/capture sizes, paginate domain endpoints, index public-token lookup, cache derived summaries where measurements justify it, and implement retention and expired-session cleanup. Benchmark representative long-lived data with concurrent bot and web traffic. SQLite can remain the initial deployment backend if the measured workload and single-host constraints support it; PostgreSQL integration is necessary before claiming PostgreSQL support or broader scaling.

### A12. Make data governance and domain integrity explicit

Records use unversioned JSON with application-only references; audit rows generally record an action and result ID rather than before/after changes. Guild deletion cascades its audit records. There is no complete member export/anonymization/deletion workflow. These are operational gaps even without asserting any particular legal requirement.

Add payload versions, validation/repair preflight, correction history for finalized wars, explicit retention rules, guild/member export and deletion procedures, and a policy for surviving administrative audit evidence. Use typed relational models where referential integrity or indexed queries materially benefit the domain. Map to WAR-08/09, OPS-08, SEC-06.

### A13. Validate an empty installation and real integrations

The UI still describes local setup and preview-only delivery, while the working-tree scheduler can send when enabled. Complete first-run onboarding, useful empty/error states, settings validation feedback, integration status, and remaining accessibility/mobile checks. Preserve the existing contributor reservations in `READINESS.md`.

Run Discord staging acceptance for OAuth, role revocation, multiple BDO guilds on one server, commands, cards, welcome roles, tickets, reminders, and restarts. Current BDO capture calibration and authentic regional screenshots remain unverified. If capture is part of the launch promise, finish durable capture handoff and current-patch verification; otherwise explicitly disable or label that feature experimental. Twitch/Ollama likewise require live checks only if included in the deployed offering. Map to AUTH-05, remaining UX tasks, WAR-06/07, LIVE-01/02/04.

## Suggested delivery order and launch acceptance

1. **Correctness and privacy:** A01–04 and the test regressions. Acceptance: private-field matrix passes; malformed settings cannot persist; mixed queues make progress; HTTPS Compose startup succeeds.
2. **Safe operation:** A05–09. Acceptance: slow integrations do not block unrelated writes; oversized/abusive requests are bounded; no administrator credentials appear in routine logs; alerts detect stopped jobs; a fresh-host restore and failed-upgrade recovery succeed.
3. **Reproducible release:** A10 and the required parts of A11–12. Acceptance: one automated gate passes from a clean checkout, a built image serves all workflows, supported capacity and retention are documented, and scans have reviewed results.
4. **Staging and pilot:** A13. Acceptance: officers and members complete a real event/war, including permission failures and restarts; selected integrations pass; operators approve the restore, monitoring, and privacy procedures.

The existing readiness checklist is broadly sound. These audit findings supply concrete defects and acceptance criteria for prioritizing it. A complete framework rewrite, mandatory PostgreSQL migration, and every optional feature are not prerequisites for a small pilot; fixing the P1 defects and proving the selected deployment are.

## Audit limits

This is a repository audit with executable checks, not a penetration test or a certification. No live Discord/Twitch/Ollama accounts, current BDO traffic, public-host TLS/firewall, disaster recovery, image build, vulnerability database scan, historical Git secret scan, or sustained load test was exercised. A clean result on those remaining checks is still required for the corresponding production claims. Temporary detailed test logs and the isolated reproduction script are under `/tmp/openiq-audit-*` for this session.
