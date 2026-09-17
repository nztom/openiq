# Guild readiness checklist

Historical implementation checklist, retained as evidence. **Do not claim work
from this checklist or treat its unchecked boxes as the current backlog.**
Use the [task register](../tasks/README.md) and
[feature state](../tasks/FEATURE_STATE.md) for ownership, dependencies and
current deployment boundaries. Later task evidence supersedes older claims
below, including bot connectivity and host rehearsal status.

## 1. Identity and initial setup

Progress reviewed on 2026-09-12: AUTH-01–04, BOT-01–02, and WAR-01–04
are implemented. PR #3's completed UX subtasks are recorded below; their parent
tasks remain open. Command sync is validated with mocked Discord responses;
live installation checks remain outstanding.

- [x] **AUTH-01 — Rotating backend recovery administrator.** Compose enables one
  Django admin account, rotates its generated password on every web start, writes
  it to a private mode-0600 credential file, and can disable the account through
  configuration. Routine logs contain only the file path.
- [x] **AUTH-02 — Discord-only member login.** Present the normal production
  login landing page with a Discord OAuth entry point. Keep password login
  available only behind an explicit development setting; `/admin/` remains
  available to the rotating backend administrator.
- [x] **AUTH-03 — Verified Discord guild onboarding.** Persist the OAuth guild
  claims in the server-side session and allow creation only for a Discord server
  where the user is owner, administrator, or has Manage Guild.
- [x] **AUTH-04 — Secure OAuth lifecycle.** Handle denied authorization, missing
  refresh tokens, account reuse, logout/session cleanup, and safe refresh failure
  messages without exposing credentials.
- [x] **AUTH-05 — First-run setup screen.** Let an authorized Discord owner select
  a server, set region and guild name, configure the bot invite, and see which
  setup steps remain.
  Verified server selection, region/name validation, invite setup and failed-save
  recovery pass server and Chromium tests at 390px.
- [x] **AUTH-06 — Guild recovery constraints.** Require verified Discord authority
  when applying an adoption key and audit both its issuer and redeemer.

## 2. Discord bot

- [x] **BOT-01 — Embedded bot runtime and secrets.** Run one supervised bot in
  the web container so it shares SQLite storage and signing-key context, with
  restart behavior, secret-file wiring, and an explicit outbound-delivery switch.
- [x] **BOT-02 — Development-guild command sync.** Support fast guild-scoped sync
  as well as global sync, document both modes, and report sync failures clearly.
- [x] **BOT-03 — Native slash-command options.** Replace the generic JSON argument
  box with typed Discord inputs, choices, autocomplete where useful, and command
  descriptions generated from the command catalog.
- [x] **BOT-04 — Discord-safe responses.** Present domain results as readable
  messages or files, paginate output beyond Discord limits, and map validation
  and permission failures to stable user-facing responses.
- [x] **BOT-05 — Persistent interactive components.** Restore signup and welcome
  views after bot restart and reject stale, malformed, cross-guild, or replayed
  component identifiers.
- [x] **BOT-06 — Event message lifecycle.** Create and update signup cards,
  capacities, waitlists, locks, archive state, recurrence, and missing-response
  reminders through Discord.
- [x] **BOT-07 — Ticket lifecycle.** Create private channels, synchronize replies,
  close/reopen tickets, retain transcripts, and reconcile partial remote failures.
  Reopen is officer-only and preserves replies. Retry recovers channels by their
  ticket marker and messages by their delivery footer; an unresolved remote
  outcome stops for inspection instead of creating a duplicate. Offline failure
  and permission regressions pass; live Discord verification remains LIVE-01.
- [x] **BOT-08 — Welcome and role lifecycle.** Post welcome cards, grant only
  configured roles below the bot role, remove obsolete selections where desired,
  and explain Discord hierarchy/permission failures.
  Remote grants verify Manage Roles, reject managed/everyone/higher roles, and
  optionally replace roles previously granted by OpenIQ. Six welcome/component
  tests pass; live role hierarchy verification remains LIVE-01.
- [ ] **BOT-09 — Scheduler delivery.** Deliver due reminders exactly once with
  retry/backoff and restart-safe idempotency instead of leaving scheduled work as
  previews.
  - [x] Durable claims, exponential retries, rate-limit handling, cancellation,
    and recovery of remotely created messages are implemented and tested.
  - [ ] An unconditional exactly-once guarantee cannot be established across
    Discord and the local database: ambiguous missing-message outcomes require
    operator reconciliation. Validate this behavior in the staging guild before
    accepting the delivery guarantee.
- [x] **BOT-10 — Bot diagnostics.** Add an operator command/check that verifies
  token validity, guild installation, intents, channel access, role hierarchy,
  and command registration without sending messages.
  `python manage.py bot_diagnostics --guild ID` reports installation, channel
  overwrites, welcome hierarchy, required intents and missing commands using GET
  requests only. Token failures are redacted; offline diagnostics tests pass.

## 3. War management end to end

- [x] **WAR-01 — Explicit score review.** OCR/CSV imports require correction of
  unmatched or ambiguous participants before finalization.
- [x] **WAR-02 — War metadata and relationships.** Recorded wars support opponent,
  result, score, event links, live-session links, relinking, and safe deletion.
- [x] **WAR-03 — Full browser lifecycle.** Browser smoke coverage exercises roster,
  event, OCR review, correction, finalization, live linking, and debrief.
- [x] **WAR-04 — Replay-scoped debrief.** Live-war summaries can isolate replay
  segments and remain connected to the finalized war.
- [x] **WAR-05 — Operational war checklist.** Provide a single pre-war/during-war/
  post-war view showing event, signup state, capture state, review state, finalized
  result, outstanding corrections, and Discord delivery state.
  History includes an officer-only derived checklist with unlinked capture and
  import work shown explicitly. Guild/member isolation and JS syntax checks pass.
- [x] **WAR-06 — Capture handoff durability.** Authenticate capture submissions,
  resume after disconnect, deduplicate retries, expose last-seen state, and retain
  a bounded diagnostic log.
  Session-scoped expiring bearer credentials, retained JSONL forwarding, deduped
  acknowledgements, last-seen and 50-entry diagnostics have offline regressions.
- [x] **WAR-07 — Import compatibility report.** Validate all supported synthetic
  CSV/OCR/IKUSA/JSONL inputs from one command and produce a clear operator report.
  - [x] `verify_imports` reports all four formats and exits nonzero on failure;
    report regressions and real CSV/IKUSA/JSONL fixture checks pass.
  - [x] Real OCR fixture gate passes with Tesseract 5.4 installed.
- [x] **WAR-08 — Export and correction history.** Export a complete war package and
  retain an audit trail when finalized participant scores or metadata are edited.
  Officer exports include linked events, captures, imports and before/after
  corrections. Regression checks cover edits, deletion history and member denial.
- [x] **WAR-09 — Retention controls.** Configure retention for raw captures, OCR
  uploads, public recaps, and derived summaries without deleting finalized wars.
  Owner retention settings control saved capture events, extracted import rows,
  public links and retained summaries. The preview-first `retention` command
  preserves live sessions and finalized wars. Uploaded OCR images are not stored.

## 4. Self-hosted operations and data safety

- [x] **DB-01 — Database backend abstraction.** Isolate connection settings and
  snapshot operations behind adapters; preserve Django ORM for domain queries,
  SQLite defaults, and shared Compose settings. PostgreSQL configuration and
  custom adapter registration are tested without a server.
- [x] **DB-02 — PostgreSQL integration.** Add a locked driver, migration/concurrency
  tests on PostgreSQL, native snapshot/restore, and a SQLite data-transfer runbook.
  psycopg is pinned; real PostgreSQL 17.11 migration, concurrent mutation and
  native snapshot/restore tests pass. Client/server version requirements and
  SQLite transfer are documented in DATABASES.md.

- [x] **OPS-01 — Production environment contract.** Supply every required and
  optional environment variable through Compose, validate unsafe/missing values
  at startup, disable demo data by default, and provide a deployment-oriented
  example file without secrets.
  Compose shares persistent-key/runtime settings, exposes optional Twitch/Ollama
  settings, disables demo seeding by default, and validates the environment before
  startup. Production OAuth and invalid boolean/delivery configurations are tested.
- [x] **OPS-02 — Consistent backup command.** Create timestamped SQLite backups
  using SQLite's online backup API, include the signing key and a manifest, and
  support a retention count without stopping the services.
- [x] **OPS-03 — Verified restore command.** Validate a backup manifest, refuse an
  accidental overwrite unless explicitly requested, restore atomically, and run
  Django checks before reporting success.
  SQLite restore verifies checksums/integrity and runs Django/migration checks in
  staging before publishing the directory. Overwrite retains the previous
  directory. A real temporary-database backup/restore drill and regressions pass.
- [x] **OPS-04 — Scheduled backups.** Run backups from the web container only
  when an operator mounts a backup directory, and document a restore drill.
  The web container takes an immediate snapshot and then runs at the configured
  interval (four hours by default), including a final snapshot on graceful
  shutdown. See [backup operations](BACKUPS.md) for the isolated restore drill.
  Scheduler tests pass; live Docker rehearsal remains LIVE-03.
- [x] **OPS-05 — Readiness and diagnostics.** Separate liveness from readiness and
  report database access, migrations, writable storage, bot/scheduler heartbeat,
  and version without revealing secrets.
  `/healthz/` is liveness; `/readyz/` and `diagnostics` verify database, migration,
  storage and configured process heartbeats. Failure/expiry and bot checks pass.
- [ ] **OPS-06 — Graceful process behavior.** Confirm signal handling, shutdown,
  startup ordering, SQLite contention handling, and recovery after abrupt process
  termination for web, scheduler, and bot.
  - [x] Scheduler restores signal handlers, stops between work items and clears
    its heartbeat. Abrupt SQLite writer rollback and PostgreSQL concurrency pass.
  - [ ] Rehearse Gunicorn/Compose shutdown and restart on the target Linux host.
- [x] **OPS-07 — Upgrade workflow.** Document pull/build/migrate/backup/rollback
  steps and add a preflight command that checks the current data before upgrade.
  `preflight` checks migrations, owners and war relationships without changing
  records. UPGRADES.md covers backup, all writer services and rollback data rules.
- [x] **OPS-08 — Structured maintenance tools.** Add supported commands for user
  removal, Discord relinking, guild export, guild deletion, expired-token cleanup,
  and audit/outbox retention.
  Owner-scoped `maintain` operations preview mutations, require explicit apply,
  protect the last owner and other guild memberships, and exclude credentials
  from exports. Cleanup preserves finalized war correction history.

## 5. Security and privacy

- [x] **SEC-01 — Production security settings.** Validate allowed hosts, trusted
  origins, TLS/proxy settings, secure cookies, HSTS options, and production Django
  deployment checks.
  Startup validates explicit hosts, HTTPS OAuth/origins and HSTS ranges. Secure
  cookies/redirects and optional HSTS policies are wired through Compose. Django
  `check --deploy --fail-level WARNING` passes with a complete TLS/HSTS configuration.
- [x] **SEC-02 — Request and login abuse controls.** Rate-limit OAuth starts,
  callbacks, recovery attempts, OCR uploads, and mutation endpoints with useful
  retry responses.
  Database-backed per-minute budgets cover OAuth, recovery, OCR and mutations
  across workers/restarts. Responses include Retry-After; identity keys are hashed.
- [x] **SEC-03 — Session and secret hygiene.** Define session lifetime, rotate
  sessions at login, clear Discord tokens at logout, redact credentials from
  errors/logs, and document secret rotation.
  Logins set an absolute expiry and clear prior Discord state; logout flushes
  the server session. Logs redact credentials/callback codes, and Gunicorn logs
  omit query strings. Rotation and logout regressions pass.
- [x] **SEC-04 — Upload hardening.** Enforce content signatures, decoded dimensions,
  processing timeouts, temporary-file cleanup, and aggregate request limits for
  OCR inputs.
  Verified PNG/JPEG/WebP decoding, 20-megapixel image limits, streamed 12-MiB
  aggregate limits, engine/request budgets and real temporary-file cleanup pass.
- [x] **SEC-05 — Permission regression matrix.** Verify owner/admin/member and
  unauthenticated behavior for every HTTP action, Discord command, component, and
  private/public record type.
  Catalog and internal HTTP actions plus every command have anonymous/lower-role
  denial coverage. Existing owner/member lifecycle and signed component regressions
  cover admitted behavior; private record and unrelated guild directory leaks are closed.
- [x] **SEC-06 — Privacy controls.** Document stored Discord/game data and provide
  guild-member export, unlink, anonymization, and deletion workflows.
  My Stats exposes scoped self-service controls; officers can act for a member.
  Deletion removes membership/identifiers and owned private records while keeping
  anonymous finalized scores. Other guild memberships remain intact. Tests pass.

## 6. Product completion and operator experience

UX reconciliation (2026-09-12): merged PR #3 and the contributor's published
`ux/dashboard-feedback` branch both end at `4dff36d`. No newer UX PR or branch
commit is published. UX-01a/b/c, UX-03a, and UX-04a/c are complete and verified
with three browser regressions. The unchecked parent items below retain their
remaining scope. The user authorized completion of the remaining tasks here;
this work builds on the contributor's existing forms and browser checks.

- [x] **UX-01 — Complete settings forms.** Replace remaining raw nested settings
  edits with validated forms for roles, channels, tickets, recruitment, schedules,
  capture, retention, and integrations.
  Typed server validation and owner forms cover the remaining nested settings.
  Chromium verifies capture error recovery, retention/integration saves and reload.
  - [x] **UX-01a: Editable schedule forms.** Show weekly/sync summaries, load
    existing settings, use weekday names, validate hour/timezone input, and
    preserve unrelated settings. Browser regression verifies save and recovery.
  - [x] **UX-01b: Application forms and ticket categories.** List, create, and
    edit saved questions, channels, names, and staff roles with validated forms
    and empty states. Browser checks cover correction, updates, and persistence.
  - [x] **UX-01c: Channel destinations.** Show and edit bot, gear, welcome,
    event, and coaching channels with ID validation, explicit blank defaults,
    and preservation of unrelated settings. Browser regression covers saves
    and validation recovery.
- [x] **UX-02 — Setup and integration status.** Show Discord bot, OAuth, Twitch,
  capture, scheduler, backup, and delivery status with actionable diagnostics.
  Settings distinguishes configured providers, process heartbeats, received capture
  batches and queued delivery, with operator next steps and no credential exposure.
- [x] **UX-03 — Empty/error/loading states.** Make every dashboard section usable
  with no demo data and preserve entered values after validation failures.
  - [x] **UX-03a: Shared table and form feedback.** Explain empty tables, show
    saving state, prevent duplicate submission/dismissal while pending, retain
    entered values on failure, and focus the error for correction.
  - [x] **UX-03b: Section-specific states.** Verify every dashboard section with
    no demo data and complete its empty, error, and loading states.
    All 12 sections pass empty-guild browser checks at 390px and 1280px.
    Refresh failures retain the current view, announce the error and recover;
    guild switches clear old data and obsolete responses cannot replace new ones.
- [ ] **UX-04 — Accessibility and mobile pass.** Verify keyboard operation, focus,
  labels, contrast, reduced motion, narrow layouts, and screen-reader announcements
  for dynamic workflows.
  - [x] **UX-04a: Shared accessibility and mobile improvements.** Name guild/action
    selectors and dialogs, expose the current section, retain navigation focus,
    add visible focus outlines and reduced-motion styles, and constrain mobile
    toast sizing. Verify empty history at 390px, keyboard navigation, and
    failed-save correction with the opt-in Chromium browser regression test (set `OPENIQ_BROWSER_CHANNEL=msedge` to use Edge):
    `OPENIQ_BROWSER_TEST=1 python manage.py test guilds.test_ux_browser`.
  - [x] **UX-04c: Roster search keyboard continuity.** Keep the search input
    focused while typing and name the search, sort, and class-filter controls.
    Browser regression verifies uninterrupted multi-character input.
  - [ ] **UX-04b: Full accessibility and mobile verification.** Complete the
    section-by-section keyboard, labels, contrast, narrow-layout, and
    screen-reader checks for dynamic workflows.
    - [x] All sections at 390px/1280px and all available action dialogs pass
      automated axe WCAG A/AA checks, keyboard navigation/dismissal and layout
      checks. Scrollable tables are named and keyboard-focusable; refresh/save
      feedback has status/alert semantics and accessibility-tree coverage.
    - [ ] A person using a screen reader must verify spoken announcements and
      workflow usability during guild acceptance; automated ARIA checks cannot
      establish that experience.
- [x] **UX-05 — Guild-cluster boundaries.** Test two BDO guilds on one Discord
  server and allied guilds in separate servers without data or permission leakage.
  Shared-server role/autocomplete isolation, HTTP mutation denial, limited allied
  roster visibility, private-record exclusion and revocation after leaving pass.
- [x] **DOC-01 — Production runbook.** Document Discord application creation, OAuth
  redirect, bot install permissions, first-run setup, backups, upgrade, recovery,
  diagnostics, and shutdown.
  RUNBOOK.md links the full host/Discord/onboarding/operations workflow and
  distinguishes local diagnostics from the required installation acceptance.
- [x] **DOC-02 — Remove prototype contradictions.** Keep README, contracts, feature
  matrix, test totals, Compose defaults, and UI wording aligned with actual
  production behavior.
  README, feature status and contracts describe enabled delivery, verified setup,
  database support and remaining live checks; stale fixed test/command totals
  were removed. The dashboard identifies a guild workspace rather than a prototype.
- [x] **QA-01 — Offline release gate.** Run Django checks, full statement/branch
  coverage, bot registry checks, OCR fixtures, packet fixtures, JavaScript syntax,
  Compose config validation, and the browser lifecycle from one command.
  `python scripts/release_gate.py` passes the complete offline gate with the
  unchanged 100% statement/branch threshold. It uses disposable data and covers
  real Tesseract fixtures, Chromium lifecycle/accessibility and Compose config.
  Native PostgreSQL restore and concurrent mutation checks also passed separately.

## External launch checks

These checks cannot be completed from synthetic data or without the chosen host.
They still block calling a specific installation live-ready.

- [ ] **LIVE-01 — Discord staging guild.** Exercise OAuth, bot install/sync,
  commands, buttons, roles, tickets, reminders, restarts, and permission failures.
- [ ] **LIVE-02 — Current BDO data.** Calibrate and verify capture against the
  current patch and test OCR/roster imports with representative regional data.
- [ ] **LIVE-03 — Hosting rehearsal.** Verify TLS, reverse proxy, DNS, firewall,
  persistent storage, scheduled backups, restore, monitoring, and upgrades on the
  selected Ubuntu host.
- [ ] **LIVE-04 — Guild acceptance.** Run one full event and war with officers and
  members, review privacy/retention policy, and record sign-off on the workflow.
