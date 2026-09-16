# Upgrade and rollback

Keep the current application commit, environment file and a private off-host
backup before upgrading. Rehearse the new revision against a restored copy first.

1. On the current revision, run `docker compose exec web python manage.py preflight`.
   Resolve missing owners or broken record links before proceeding.
2. Create a backup with `docker compose exec web python manage.py backup --output /backups`.
   This requires the operator-controlled `/backups` mount described in
   [BACKUPS.md](BACKUPS.md); verify its manifest and keep the completed snapshot
   off the application data volume.
3. Stop all writers, including optional profiles:
   `docker compose --profile jobs --profile discord down`.
   Do not use `down -v`. Record which profiles were enabled.
4. Pull the reviewed release (`git pull --ff-only` on the deployment branch),
   review changes to `.env.example`, and set `OPENIQ_VERSION` to the new commit.
   Run `docker compose build` and `docker compose config --quiet`.
5. Start web first with `docker compose up -d web`. Its entrypoint validates
   configuration and runs migrations before Gunicorn. Inspect web logs and run
   `docker compose exec web python manage.py preflight`.
6. Start the previously enabled profiles. Check `/readyz/`, operator diagnostics,
   a known guild/war, and the age of the most recent backup before reopening access.

For rollback, stop all writers and rebuild the previously recorded commit. If
migrations or new writes changed the data, restore the pre-upgrade snapshot with
the matching revision using [the offline restore procedure](BACKUPS.md). Never
assume an older application can read a newly migrated database. Keep the failed
deployment's data separately for investigation. Rollback loses post-backup writes;
obtain the guild's acceptance of the recovery point before discarding them.

The container entrypoint uses `exec` so signals reach the service. Scheduler
shutdown stops between guilds/messages and records an unavailable heartbeat;
remote calls already in flight finish or hit their timeout. Backup shutdown
allows an active snapshot to finish. PostgreSQL and SQLite concurrency/rollback
behavior is tested locally; Gunicorn, Compose startup order and abrupt Linux
container termination still require the LIVE-03 hosting rehearsal.
