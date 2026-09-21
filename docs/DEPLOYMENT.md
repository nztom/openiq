# Docker and Swarm deployment

These are production-oriented examples. Copy their environment templates to
private, ignored files; do not put credentials, Docker secrets, databases, or
backups in Git.

## Standard Docker Compose

The repository's `compose.yaml` is the full local stack. For a small,
single-service production deployment with mounted backups, use the standalone
example instead:

```sh
cp examples/compose.env.example examples/compose.env
mkdir -p backups
# Edit examples/compose.env: set the public hostname, HTTPS origin, and Discord OAuth values.
docker compose --env-file examples/compose.env -f examples/docker-compose.yaml up --build -d
docker compose --env-file examples/compose.env -f examples/docker-compose.yaml ps
docker compose --env-file examples/compose.env -f examples/docker-compose.yaml logs --tail=100 web
```

It builds `openiq:local`, stores SQLite and the generated signing key in the
local `openiq-data` named volume, and mounts `BACKUP_HOST_DIRECTORY` as
`/backups`. The web container runs backups only while that mount exists. The
default interval is 14,400 seconds (four hours); on a graceful stop it makes
one final snapshot. Keep the backup directory outside the application data
volume and copy it to separate storage.

To use an already-built image, set `OPENIQ_IMAGE` and remove `build: ..` in a
private override. The application listens on HTTP port `8000` inside the
container. Terminate TLS at a trusted proxy, set `HTTPS=1` and `TRUST_PROXY=1`,
and route the proxy to `http://OPENIQ_HOST:8000`; do not use HTTPS for that
internal upstream unless a separate TLS proxy is installed there.

## Docker Swarm

The Swarm example keeps SQLite on a Docker **local** volume. It must not be
placed directly on NFS. A NAS-backed `/backups` bind mount is used only for
verified snapshots. If Swarm schedules the single replica onto another eligible
node with an empty local volume, OpenIQ restores the latest verified snapshot
from `/backups` before starting. A hard node failure can therefore lose up to
one backup interval; the graceful-stop final backup normally reduces that.

Before deployment, make the same NAS mount available at the same absolute path
on every node that carries `openiq_data=true`, and create the external overlay
network once:

```sh
docker network create --driver overlay edge
docker node update --label-add openiq_data=true NODE_NAME
docker secret create openiq_secret_key ./private/openiq_secret_key
docker secret create openiq_discord_client_secret ./private/discord_client_secret
docker secret create openiq_discord_bot_token ./private/discord_bot_token
```

Create private Swarm deployment variables (for example
`private/openiq-swarm.env`):

```dotenv
OPENIQ_IMAGE=registry.example.invalid/openiq:COMMIT_SHA
BACKUP_HOST_DIRECTORY=/mnt/nas/openiq/backups
OPENIQ_PROXY_NETWORK=edge
ALLOWED_HOSTS=openiq.example.com,localhost
CSRF_TRUSTED_ORIGINS=https://openiq.example.com
DISCORD_CLIENT_ID=YOUR_DISCORD_APPLICATION_ID
DISCORD_REDIRECT_URI=https://openiq.example.com/auth/discord/callback/
ENABLE_DISCORD_DELIVERY=0
RUN_DISCORD_BOT=0
RUN_SCHEDULER=0
SCHEDULER_INTERVAL=30
DISCORD_SYNC_GLOBAL=1
DISCORD_SYNC_GUILD=
```

Build an immutable image and make it reachable by every Swarm node. Substitute
your registry; never deploy a mutable tag such as `latest`:

```sh
IMAGE=registry.example.invalid/openiq:$(git rev-parse --short=12 HEAD)
docker build --pull --tag "$IMAGE" .
docker push "$IMAGE"
```

Load the private variables into the shell using the method appropriate for your
shell or CI, then deploy and inspect the stack:

```sh
docker stack deploy --with-registry-auth -c examples/swarm-compose.yaml openiq
docker service ls
docker service ps openiq_web
docker service logs --tail=100 openiq_web
```

The stack name `openiq` produces the service name `openiq_web`. A Cloudflare
Tunnel or equivalent proxy on the `edge` overlay should use
`http://openiq_web:8000` as its origin. Public TLS is handled by Cloudflare;
OpenIQ receives HTTP from that trusted proxy. Verify both `/healthz/` and the
public HTTPS hostname after each deployment.

Docker secrets are mounted as files and consumed through `*_FILE` environment
variables. Keep ordinary non-secret settings in the private deployment
environment file. The examples deliberately leave Discord delivery and the
embedded bot off. To enable it, create the bot-token secret, set
`ENABLE_DISCORD_DELIVERY=1` and `RUN_DISCORD_BOT=1`, and choose exactly one
command-sync mode. The bot runs in `openiq_web`, so it always shares that
service's node-local SQLite database.

## Upgrade and recovery checks

1. Confirm `docker service ps openiq_web` has one running task and inspect its
   logs for a successful migration and current backup.
2. Before changing nodes, verify the backup mount holds a recent
   `openiq-backup-*` snapshot with its manifest.
3. After a controlled update, the stop grace period allows the final backup to
   complete. After an ungraceful failover, inspect the logs for the verified
   restore message before accepting traffic.
4. Rehearse the isolated restore process in [BACKUPS.md](BACKUPS.md) before
   relying on these recovery properties.

## Scheduled jobs

Set `RUN_SCHEDULER=1` to run the application scheduler as a supervised child of
the single `web` replica. It uses the same `/data/db.sqlite3`, automatically
adds `scheduler` to readiness requirements, stops with the web process, and
causes the container to restart if it exits unexpectedly. Keep the web service
at one replica so exactly one scheduler owns the node-local SQLite database.

When disabled, reminder, recurrence, summary, roster-sync, and outbox jobs do
not run automatically; operators must run `python manage.py tick` in the web
container. Discord sends additionally require explicit delivery enablement.
Do not add a separately schedulable Swarm service with local SQLite because it
could run against a different node's database. The root development Compose
file may still use its node-local `jobs` profile.
