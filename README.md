# OpenIQ

**OpenIQ is unapologetically developed entirely with AI, with minimal human oversight.**

A self-hosted guild-management application for Black Desert guilds. Django with SQLite or PostgreSQL powers independent domain modules; the browser UI uses HTML/CSS/JavaScript.

**Status:** locally validated platform with fixtures, reviewed imports and optional external adapters. A calibrated TCP/PCAP decoder is implemented and tested with synthetic captures; its historical calibration is not verified against the current BDO patch. The Discord bot has connected and synced commands on the Pi Swarm, while OAuth, delivery workflows, and Twitch still need live acceptance. See the [feature state](tasks/FEATURE_STATE.md) and [task register](tasks/README.md) for precise boundaries and planned work.

See the [production runbook](docs/RUNBOOK.md) for Discord application setup, first-run onboarding and daily operations.

## Run with Docker

For the compact single-host Compose example and the production Swarm stack
example, see [Docker and Swarm deployment](docs/DEPLOYMENT.md). Both examples
are credential-free templates; keep their copied environment files private.

```bash
cd /home/user/src/openiq
cp .env.example .env
# Configure Discord OAuth, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS and your TLS proxy.
docker compose up --build -d
```

Open your configured **HTTPS address** and sign in through Discord. Normal member
login is Discord-only. The `openiq-data` named volume persists the database and
signing key across container replacement. Existing host data is not copied into
the image or container.

```bash
# Inspect status and logs.
docker compose ps
docker compose logs --tail=100 web

# Enable the optional continuous scheduler (delivery follows its explicit switch).
docker compose --profile jobs up -d

# Set RUN_DISCORD_BOT=1 in .env after setting its token and enabling delivery,
# then restart web.
docker compose up -d web

# Stop containers while retaining data.
docker compose down
```

For Docker without Compose:

```bash
docker build -t openiq:local .
docker run -d --name openiq -p 127.0.0.1:8765:8000 \
  -v openiq-data:/data --env-file .env openiq:local
```

The application runs as UID 10001, includes Tesseract and uses Gunicorn/WhiteNoise to serve the app and static assets. It does not require a host Python installation. `.dockerignore` excludes the host database, signing key, environment files, Git metadata, virtual environment and screenshots.

Copy `.env.example` to `.env` to customize the deployment. Set the Discord OAuth
variables before normal use. `ALLOW_LOCAL_LOGIN=1` exposes the password form for
development fixtures only (also set `DEBUG=1`, `HTTPS=0`, and an explicit demo
password if enabling `SEED_DEMO=1`); leave it disabled for a guild installation. `HTTPS=1`
enables secure cookies and HTTPS redirects when deployed behind TLS; set
`TRUST_PROXY=1` only for a trusted reverse proxy that controls forwarded headers.

Compose enables one break-glass Django backend account by default. Each web-container start creates or rotates its random password and writes the `/admin/` credential to `/data/.backend-admin.json` with mode 0600; startup logs contain only the file path. Retrieve it through private operator access with `docker compose exec web cat /data/.backend-admin.json`. The scheduler never rotates it. Set `ENABLE_BACKEND_ADMIN=0` to disable the account and remove that file on the next web start, or change its stable username with `BACKEND_ADMIN_USERNAME`. This account is for backend recovery and inspection, not normal guild membership.

The Docker container hosts the platform. The desktop/live-interface capture process remains on the game host; offline PCAP parsing can also run in the image. No privileged container or host-network mode is required for the dashboard.

## Run on Ubuntu Desktop

```bash
cd /home/user/src/openiq
python3 -m venv .venv
.venv/bin/pip install -r requirements.lock
.venv/bin/python manage.py migrate
ALLOW_LOCAL_LOGIN=1 .venv/bin/python manage.py seed_demo
ALLOW_LOCAL_LOGIN=1 .venv/bin/python manage.py runserver 127.0.0.1:8765 --noreload
```

Open **http://127.0.0.1:8765/**. Demo accounts:

| Username | Role | Default password |
|---|---|---|
| `demo` | Owner | `prototype-local-2026` |
| `officer` | Admin | `prototype-local-2026` |
| `member` | Member, linked to Juniper | `prototype-local-2026` |

Set `DEMO_PASSWORD` before the first seed to choose a different demo password. Seeding is idempotent and does not reset existing credentials. This is a localhost development server, not a production deployment. Use `createsuperuser` for Django administration if needed.

## Try the workflows

1. **Members:** add/edit a family, set class, add vacation/notes, toggle exception, or switch to the draggable group board.
2. **History:** record a war with editable participant rows; import `fixtures/scores.csv` through Review scores and finalize the review. Change exclusions and alliance sharing separately.
3. **Signups:** join a capacity-limited team; overflow is waitlisted. Withdraw or drag members between teams. Save presets, repeat an event, lock/archive it and preview its Discord card.
4. **Performance:** configure thresholds, create a lead, assign and resolve mentoring. Link an event to its recorded war for no-show reconciliation.
5. **Gear:** update gear and inspect history; deletion clears the current display without losing history. Add reviewed rival snapshots for guild rankings.
6. **Live War:** start a session, generate a synthetic fight, import `fixtures/combat.jsonl`, or paste `fixtures/ikusa.log` into Import IKUSA text log with the date/timezone. Save, replay, link a war and enable/revoke a public recap.
7. **Alliance:** as `demo`, invite Silver Meridian, switch guild and accept. Only explicitly shared wars contribute.
8. **Community:** open/reply/close tickets; apply/review recruitment; generate welcomes, reminders, summaries, rolls and the enhancement minigame. Notifications stay as previews until explicit delivery is enabled.
9. **Settings:** configure roles, channels, schedules, create ticket categories and application forms, run scheduled work, and inspect the audit trail.

Real OCR uses the system `tesseract` executable (`sudo apt install tesseract-ocr` if absent). Upload cropped names/stat panels in alternating pairs. Misaligned or ambiguous results require correction; they never silently finalize a war. Gear OCR recognizes labeled AP/AAP/DP text and always requires review. The checked-in dark score panels are deterministic synthetic BDO-style regression inputs, not authentic game screenshots; regenerate them with `scripts/generate_ocr_fixtures.py`.

## Module layout

Each module exposes `handle(guild, action, payload, role, user)` and uses shared transactional dispatch. Browser routes and Discord commands call the same service boundary.

- `guilds/modules/roster.py`: roster, groups, class changes, identity links, notes, vacations, merge.
- `wars.py`, `analytics.py`, `intelligence.py`: reviewed scores, war history, metrics, awards, character lookup records and opponent profiles.
- `events.py`, `coaching.py`, `gear.py`, `alliances.py`: independent guild domain workflows.
- `community.py`, `operations.py`, `adminops.py`: support/recruitment, utilities, jobs, settings and access.
- `integrations.py`, `logformat.py`, `guilds/capture.py`: OCR, roster HTML, Twitch and event-file adapters.
- `commands.py`, `discord_auth.py`, `delivery.py`: local command routing, optional OAuth and explicit notification delivery.

Records have a relational guild/kind/key envelope, unique constraints and module-owned JSON payloads. External AI, Twitch and roster reads are prepared before acquiring the writer lock; access, role, guild revision and configuration are checked again before committing their results. Local mutations and audit entries share a short transaction. War correction history records changed rows rather than scanning every war around unrelated actions. This targets small guild installations; PostgreSQL has native snapshot/restore and concurrency integration tests. Larger deployments still need workload-specific validation.

## Optional integrations and tools

No Discord messages have been sent. No bot has been connected.

```bash
# All registered commands are constructed without a network connection.
.venv/bin/python manage.py runbot --check

# Read-only remote checks; requires the bot token but sends no messages.
.venv/bin/python manage.py bot_diagnostics --guild 1

# Exercise commands locally.
.venv/bin/python manage.py local_command guildstats --guild 1 --user demo
.venv/bin/python manage.py local_command 'reminder list' --guild 1 --user member

# Process scheduled jobs once; sends only with ENABLE_DISCORD_DELIVERY=1.
.venv/bin/python manage.py tick

# Tail a normalized event log into an existing live session.
.venv/bin/python manage.py capture fixtures/combat.jsonl --session SESSION_ID --once

# Optional desktop file-capture companion (requires tkinter).
.venv/bin/python scripts/capture_desktop.py
```

Discord OAuth needs `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, and `DISCORD_REDIRECT_URI` (default `http://127.0.0.1:8765/auth/discord/callback/`). Configure guild `server_id` and role IDs. User OAuth requests profile, guild-list and own guild-membership read scopes. Role refresh fails closed. In production, `/login/` presents a Discord sign-in landing page; password login is available only when `ALLOW_LOCAL_LOGIN=1`. Django's separate `/admin/` login remains available for the managed recovery administrator.

The bot runs as a supervised child of the `web` container. Set
`DISCORD_BOT_TOKEN`, `ENABLE_DISCORD_DELIVERY=1`, and `RUN_DISCORD_BOT=1`, then
restart `web`. It shares the exact SQLite database and signing-key context with
the application, registers the command tree, and a bot failure restarts the
container rather than leaving the website silently degraded. The default
`DISCORD_SYNC_GLOBAL=1` publishes global commands. For a staging server, set it
to `0` and set `DISCORD_SYNC_GUILD` to the numeric server ID for immediate,
guild-scoped updates. The two sync modes are mutually exclusive. `deliver ID` only
previews an outbox item; `deliver ID --send` requires delivery enablement and a
numeric target channel. Remote behavior is covered with controlled mocks but
still needs the staging-guild launch check before a real guild depends on it.

Slash commands use native typed fields instead of a generic arguments object.
Member, war, reminder and assignment selections offer guild-scoped autocomplete;
Discord account/channel fields use native pickers. Dates use ISO text with an
explicit timezone offset for timestamps. Reviewed roster names accept commas or
newlines. `/config` accepts a named configuration section and that section's JSON
object. Large responses are private JSON attachments rather than truncated text.

Twitch uses `TWITCH_CLIENT_ID` and `TWITCH_ACCESS_TOKEN`; without them the demo directory is explicitly labeled as fixture data.

## Verification

Install `requirements-dev.txt`, Tesseract, Node, Chromium (`python -m playwright install chromium`) and the pinned accessibility tool (`npm ci`). Run the complete offline gate with `python scripts/release_gate.py`; it uses disposable data and emits `release-report.json`. Docker Compose is required for configuration validation (a standalone executable can be supplied with `--compose PATH`). Live-host checks remain separate.

Individual checks:

```bash
.venv/bin/python manage.py test
.venv/bin/python manage.py check
.venv/bin/python manage.py runbot --check
.venv/bin/python scripts/verify_ocr.py
.venv/bin/python manage.py verify_imports --output import-report.json
.venv/bin/python scripts/verify_packets.py
node --check static/app.js
```

Browser checks use optional `playwright` (`pip install -r requirements-dev.txt`, then `playwright install chromium`). With the server running, execute `scripts/browser_smoke.py`. The script uses the default Playwright browser location; set `PLAYWRIGHT_BROWSERS_PATH` if you installed browsers elsewhere. Screenshots are in `docs/dashboard.png` and `docs/mobile.png`. Install the pinned accessibility engine with `npm ci`; opt-in dashboard/onboarding checks run with `OPENIQ_BROWSER_TEST=1 python manage.py test guilds.test_ux_browser guilds.test_onboarding_browser`.

## Configuration and data

Operator maintenance uses `python manage.py maintain OPERATION --guild ID --actor OWNER`.
Operations are `export` (`--output private.json`), `remove_user` (`--username USER`),
`relink_discord` (`--username USER --member MEMBER_ID --discord-id ID`),
`delete_guild` (`--confirmation GUILD_NAME`), and `cleanup` (`--days 90`). Mutations
preview by default and require `--apply`. Removing guild access preserves other
guild memberships; the local account is removed only when no memberships remain
and it is not a backend administrator. Cleanup removes expired capture/adoption
credentials and old audit/completed outbox records, preserving finalized wars
and their correction history. Exports are private and exclude credentials.

`/healthz/` checks web-process liveness. `/readyz/` and `python manage.py diagnostics`
check database access, migrations, writable storage and optional process heartbeats.
Set `REQUIRED_PROCESSES=scheduler` when the scheduler profile is enabled. The web
entrypoint automatically requires the bot heartbeat when `RUN_DISCORD_BOT=1`; a
heartbeat older than two minutes fails readiness. Set `OPENIQ_VERSION` to the deployed commit
or release. Reports contain status flags rather than credentials or data paths.

Owners can set `retention` through the settings API with `capture_days`,
`import_days`, `recap_days`, and `summary_days` (0 disables expiry). Preview with
`python manage.py retention --guild ID`; add `--apply` to clear expired server
capture events/import rows, revoke public recaps and expire retained summaries.
Age is measured from record creation. Live sessions and finalized wars are
preserved. OCR upload images are processed in memory and not retained. Capture
source files on separate machines require their own operator cleanup policy.

Officers can choose **Export war package** in History to download the war,
participant identities, linked records and correction history. The equivalent CLI
is `python manage.py export_war --guild ID --war WAR_ID --user OFFICER --output war.json`.
The output contains private guild data; the CLI refuses to overwrite an existing file.

Database settings and maintenance operations use a pluggable backend layer;
domain queries use Django ORM. SQLite remains the supported default. See
[database extension guide](docs/DATABASES.md) for adapter contracts, PostgreSQL
configuration scaffolding, and the remaining PostgreSQL integration work.

SQLite database: `db.sqlite3`; generated signing key: `.secret-key`. Both are excluded from Git. No credentials belong in source control.

Create a consistent online backup without stopping the services:

```bash
python manage.py backup --output /path/to/private/backups --keep 7 --timeout 120
# In Compose, use the operator-mounted backup directory:
docker compose exec web python manage.py backup --output /backups --keep 7
```

Each timestamped snapshot includes `db.sqlite3`, the active `.secret-key`, and a
SHA-256 manifest. The command validates SQLite integrity before publishing the
snapshot and retains the newest requested count. Directories use mode 0700 and
files use 0600. Backups contain private guild data and credentials; store them in
an operator-controlled location outside Git and copy them off the application
disk. External Discord/Twitch secrets supplied through environment variables
need separate operator backups. The web container schedules snapshots only when
an operator mounts its backup directory; see [backup operations and restore drill](docs/BACKUPS.md).
The same guide documents the checked, staged `restore` command and its offline
overwrite/recovery requirements.

Research and independent behavior decisions: [investigation](docs/RESEARCH.md), [feature matrix](docs/FEATURES.md), [data contract](docs/CONTRACTS.md).

## Calibrated packet capture

The decoder is independently implemented from the public IKUSA field-calibration contract. The bundled offsets are **historical (2023-04-19)** and use a documentation-only server network. They are suitable for the synthetic fixture, not an assertion of current game compatibility.

```bash
.venv/bin/python manage.py packet_capture \
  --calibration fixtures/calibration-historical.json \
  --pcap fixtures/combat-synthetic.pcap
```

For an actual game session, supply a verified current calibration and explicit server network/interface selection. `packet_capture --interfaces INTERFACE --calibration FILE --session SESSION_ID` provides live capture through Scapy; Windows uses Npcap, while Linux requires capture permission. Live traffic has not been captured during development.

The local capture-release prototype can build and checksum-verify portable source packages:

```bash
.venv/bin/python manage.py release_capture --output /tmp/openiq-release
.venv/bin/python manage.py update_capture /tmp/openiq-release/manifest.json /tmp/openiq-capture-install --install
```

These are local source releases, not a published Windows executable distribution. The installer validates archive paths and checksums and replaces the installed tree atomically. A remote release service would additionally need signed manifests and platform packaging.

Optional AI text generation uses a local Ollama server when `OLLAMA_MODEL` is set, with `OLLAMA_URL` defaulting to `http://127.0.0.1:11434`. Without a model it clearly identifies its deterministic offline fallback.

## Test coverage

The release gate requires **100% statement and branch coverage** for the Python application and management commands. The gate report records the current test count and any skipped platform-specific tests. Coverage excludes test files and generated migrations. The C tracer is selected explicitly because Python 3.14's default monitoring tracer reported false missing branches for compact exception paths.

```bash
python -m pip install -r requirements-dev.txt
python -m coverage run manage.py test
python -m coverage report
python -m coverage html
python scripts/browser_smoke.py
```

The coverage report fails below 100%. Browser smoke tests separately exercise all 12 dashboard sections and representative data-entry workflows against the running container. This is not a claim of 100% JavaScript coverage or live-service parity: Discord/Twitch/Ollama calls are mocked, and packet tests use synthetic captures.

To build and inspect a portable capture source release locally:

```bash
python manage.py release_capture --release-version 0.1.0 --output /tmp/openiq-release
python manage.py update_capture /tmp/openiq-release/manifest.json /tmp/openiq-capture --install
```


## Discord ticket channels (optional)

The Community tab can preview a private ticket-channel plan. Configure `tickets.bot_user_id`, `tickets.staff_role`, and optional `tickets.category_id` through the settings API. The ticket author must have a roster entry linked to both their local account and Discord ID. Ticket categories can override the staff role.

```bash
python manage.py ticket_channel TICKET_ID --guild GUILD_ID --user demo
```

The command previews by default. Adding `--send` requires `ENABLE_DISCORD_DELIVERY=1` and `DISCORD_BOT_TOKEN`; it creates or updates a private channel, synchronizes transcript messages, and makes closed tickets read-only for their author. Officers can reopen tickets without losing replies, then synchronize again to restore sending permission. The bot needs the corresponding Discord channel/message permissions, including reading message history and embedding links. Remote behavior is tested with mocks only. Retry recovers uncertain channel creation using its topic marker and uncertain message creation using its delivery footer. If no matching remote object can be found, delivery stops for operator inspection rather than creating duplicates. Preserve those markers and run a single delivery worker per guild.


Welcome cards support native Discord role buttons. Set `welcome.roles` to allowed labels (for example `["Raider", "Social"]`) and `welcome.role_ids` to the corresponding Discord role IDs. Preview a welcome card for a linked member, then use the existing opt-in outbox delivery command to post it. The bot processes button selections only for the intended member or an officer; local role selection remains available without Discord. Remote updates require Manage Roles and unmanaged roles below the bot's highest role. Set `welcome.replace_selection=true` to remove earlier roles granted by OpenIQ when selecting a new role; unrelated Discord roles remain intact. Requests are idempotent, so retry after a partial failure to finish reconciliation. HTTP failures do not mark the local selection as successful.
