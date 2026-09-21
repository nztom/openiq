# Production operator runbook

Use one Compose project for one guild or a trusted guild cluster. SQLite is the
default; PostgreSQL setup and tested transfer/restore instructions are in
[DATABASES.md](DATABASES.md). Check the current
[feature boundaries](../tasks/FEATURE_STATE.md) and complete the relevant live
acceptance tasks before officers rely on a particular installation.

## Prepare Discord and the host

1. Create an application in the [Discord Developer Portal](https://discord.com/developers/applications).
   Record its application/client ID. In OAuth2, add exactly
   `https://YOUR_HOST/auth/discord/callback/` as an allowed redirect. Store the
   client secret in the host's private `.env`, never in Git or browser settings.
2. Create/reset the bot token in the application's Bot settings. The bot uses default, non-privileged intents. Role checks use interaction
   membership data and REST requests; these slash-command workflows do not
   require privileged Server Members or Message Content intents.
3. Install the bot with scopes `bot` and `applications.commands`. Grant View
   Channels, Send Messages, Embed Links, Read Message History, Manage Channels
   (tickets) and Manage Roles (welcome selections). The onboarding screen supplies
   an invite link. Put its highest role above every welcome role it may grant;
   configure ticket staff roles and channel overwrites deliberately. Run the
   read-only diagnostics below before enabling delivery.
4. On the Ubuntu host, install Docker Engine and Compose, clone the repository,
   copy `.env.example` to `.env`, and restrict that file to the operator. Set
   `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, all three `DISCORD_CLIENT_*`/redirect
   values, `HTTPS=1`, and the bot token when enabling the bot. The OAuth variables
   are `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `DISCORD_REDIRECT_URI`.
5. Terminate TLS at your reverse proxy and route to loopback port 8765. Use
   `TRUST_PROXY=1` only when that proxy strips incoming forwarded headers and sets
   its own. Keep `localhost` in `ALLOWED_HOSTS`: the image's loopback health
   probe uses that internal host header. Keep the application port inaccessible
   from the public network.
   Configure DNS/certificates and host firewall for the selected host.
   [SECURITY.md](SECURITY.md) covers HSTS, sessions, proxy trust and rotation.

## Start and onboard

```sh
docker compose config --quiet
docker compose up --build -d web
docker compose logs --tail=100 web
docker compose exec web python manage.py diagnostics
```

Startup validates settings, applies migrations and rotates the optional backend
administrator. Its new credential is written to `/data/.backend-admin.json` with
mode 0600. Retrieve it through private operator access using
`docker compose exec web cat /data/.backend-admin.json`; routine logs contain only
the file path. Disabling the managed account removes the file. It is regenerated
on startup and does not need a separate backup. The `/admin/` account is for backend recovery, not member access.
Demo seeding and member password login stay disabled in production.

Open the HTTPS site to reach the Discord sign-in landing page, then select
**Sign in with Discord**. A server owner, administrator or user with Manage
Guild can select a verified server, name the BDO guild and set its region. In
Settings, configure owner/admin/member role IDs, channel
destinations, ticket staff/categories, welcome selections and schedules. A user
without a matching role does not automatically gain member access. Multiple BDO
guilds may share a Discord server; set each guild's roles separately and select
`guild_name` in ambiguous slash commands.

For staging, set `DISCORD_SYNC_GLOBAL=0` and `DISCORD_SYNC_GUILD=SERVER_ID`.
Use global sync for a production installation when ready; do not enable both.
Set `ENABLE_DISCORD_DELIVERY=1` and `RUN_DISCORD_BOT=1` only after reviewing
destinations and permissions. The bot runs inside `web`; restart that service
after changing either setting.
Set `RUN_SCHEDULER=1` when automatic reminders, recurrence, summaries,
roster-sync, and outbox delivery are required. The scheduler also runs inside
`web` and automatically becomes a readiness requirement.

```sh
docker compose exec web python manage.py bot_diagnostics --guild GUILD_ID
docker compose up -d web
docker compose logs --tail=100 web
```

## Local release smoke

Run this disposable check before a host rehearsal. It builds a fresh image,
starts a separately named loopback-only Compose project, verifies liveness,
readiness, diagnostics, persistence across a web restart, and the scheduler
profile. It does not contact Discord or prove TLS/proxy behavior.

```sh
docker build --pull --no-cache --tag openiq:local .
docker compose --env-file .env.example --profile jobs config --quiet

# Use a unique project name and unused local port. These settings are only for
# the disposable local check; production requires HTTPS and Discord settings.
OPENIQ_BIND=127.0.0.1 OPENIQ_PORT=18765 HTTPS=0 DEBUG=1 \
ALLOW_LOCAL_LOGIN=1 ENABLE_BACKEND_ADMIN=0 SECRET_KEY=smoke-validation-secret-key-only \
docker compose --project-name openiq-smoke --env-file .env.example up -d --no-build web
curl --fail http://127.0.0.1:18765/healthz/
curl --fail http://127.0.0.1:18765/readyz/
docker compose --project-name openiq-smoke exec web python manage.py diagnostics
docker compose --project-name openiq-smoke restart web
curl --fail http://127.0.0.1:18765/readyz/
OPENIQ_BIND=127.0.0.1 OPENIQ_PORT=18765 HTTPS=0 DEBUG=1 \
ALLOW_LOCAL_LOGIN=1 ENABLE_BACKEND_ADMIN=0 SECRET_KEY=smoke-validation-secret-key-only \
docker compose --project-name openiq-smoke --env-file .env.example --profile jobs up -d --no-build scheduler
docker compose --project-name openiq-smoke ps

# Remove only this disposable project and its generated data when finished.
docker compose --project-name openiq-smoke down --volumes
```

The configuration command validates the optional scheduler profile. The
embedded Discord bot requires dedicated staging credentials and is covered by
the Discord staging task. Backups require an
operator-created directory mounted into the web container and an actual restore
drill, so they are covered by the host and backup rehearsal tasks rather than
this smoke check.

`GUILD_ID` is OpenIQ's numeric database ID from the dashboard API, not the Discord
server ID. Settings reports local configuration, last capture acknowledgement,
process heartbeats and the delivery queue; ?configured? does not prove that an
external provider is reachable. `/healthz/` reports web liveness. `/readyz/`
checks database, migrations and storage. `RUN_DISCORD_BOT=1` and
`RUN_SCHEDULER=1` automatically require their embedded process heartbeats.

## Operate and recover

- **Backups:** prepare the operator-owned backup directory for container UID
  10001, mount it at `BACKUP_OUTPUT` (default `/backups`) in the web container,
  and perform the isolated restore drill in [BACKUPS.md](BACKUPS.md). Keep a
  protected off-host copy including the signing key. A successful scheduled
  heartbeat is not a substitute for a restore drill.
- **Capture/imports:** follow [CAPTURE_HANDOFF.md](CAPTURE_HANDOFF.md). Use
  `verify_imports` for synthetic compatibility, then validate current regional
  game samples. Pairing credentials expire and are scoped to one live session.
- **Upgrades:** follow [UPGRADES.md](UPGRADES.md): preflight, backup, stop all
  writers, build/migrate/start, verify and keep the previous image and data copy.
- **Recovery:** use the backend administrator only to inspect/fix authorized
  state. Moving a guild to another server requires the single-use adoption key
  and a fresh verified Discord owner/Administrator/Manage Guild claim; see
  [CONTRACTS.md](CONTRACTS.md). Never edit JSON or a live database as a routine
  substitute for the supported maintenance commands.
- **Roster integrity:** run `python manage.py validate_roster` to check every
  guild, or add `--guild GUILD_ID` to limit the read-only check. The command
  reports malformed member IDs without printing roster contents. Correct each
  reported row through an owner-authorized roster edit, then rerun the check;
  do not edit the JSON database column directly.
- **Data/privacy:** `maintain` previews operator changes before `--apply`.
  [PRIVACY.md](PRIVACY.md) describes member export/unlink/anonymization/deletion;
  `retention` previews age-based cleanup. Historical war scores stay anonymous
  when member identifiers are removed.
- **Delivery failures:** inspect logs and outbox state. Rate limits retry with
  backoff; an ambiguous remote creation is marked `uncertain` for inspection. Resolve
  the remote outcome before retrying. Do not delete idempotency records merely
  to force another message. Discord and the local database cannot jointly offer
  an unconditional exactly-once transaction.

The queue stores claims and retries on `Outbox`. Retryable failures stop after
six attempts; expired sending leases become `uncertain` rather than issuing a
second blind create. Drafts with nonnumeric destinations do not consume the
delivery batch limit. Long notifications are delivered as full-text attachments.
Cancellation prevents unsent retries; a request already in flight may finish.

Use one of these commands to reconcile an `uncertain` or `failed` notification:

```sh
# Read-only Discord search, restricted to this bot's message marker.
python manage.py reconcile_delivery OUTBOX_ID --find
# Or supply the exact message ID; author and channel are verified remotely.
python manage.py reconcile_delivery OUTBOX_ID --message-id MESSAGE_ID
# Only after checking Discord and confirming that no message exists:
python manage.py reconcile_delivery OUTBOX_ID --confirm-not-sent
```

Successful reconciliation queues the notification for the next scheduler pass;
it does not send a message. A verified existing message is edited rather than
recreated. The bounded search checks at most 10,000 recent messages; an absent
match does not prove that an older message was never sent. Pre-integration local
messages may lack a footer marker, so use their explicit message IDs.

## Shutdown and installation acceptance

```sh
docker compose --profile jobs stop
# Or remove containers while preserving the named volume:
docker compose --profile jobs down
```

Do not add `--volumes` unless intentionally destroying the saved installation.
Rehearse shutdown, abrupt termination, restart and upgrade on the target Linux
host. Record staging command/button/role/ticket/reminder results, a real war and
import review, restore evidence, and officer/member acceptance in the matching
[task documents](../tasks/README.md).
Include keyboard and spoken screen-reader workflow review. Keep failed or
unavailable checks open with their reason and next action.
