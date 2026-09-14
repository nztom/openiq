# Scheduled backups and restore drill

The optional `backups` Compose profile runs the existing online backup command
immediately on startup, then waits `BACKUP_INTERVAL` seconds after each attempt
(default 86400). It retains `BACKUP_KEEP` completed snapshots (default 7).
Failures produce an error in container logs and retry at the next interval;
monitor both those logs and the age of the newest completed snapshot. Restarting
the service makes another snapshot immediately. Run only one scheduler per output
directory. SQLite is currently the supported snapshot backend.

On the Linux host, prepare a private directory writable by container UID 10001:

```sh
sudo install -d -m 700 -o 10001 -g 10001 /srv/openiq-backups
```

Set `BACKUP_DIRECTORY=/srv/openiq-backups` in `.env`, then run:

```sh
docker compose --profile backups up -d --build
docker compose logs backup
```

The bind source must already exist. Backups are outside the database volume;
copy them to separate storage for protection against host loss. They contain
private guild data and the signing key. Do not commit them to Git. The service
does not migrate, seed data, or rotate the backend administrator. Its shared
database connection settings match the web service. If configuring `SECRET_KEY`
directly on web, supply the identical value to backup as well.

`BACKUP_TIMEOUT` bounds the SQLite snapshot attempt (default 120 seconds). Keep
Compose's `stop_grace_period` longer than that timeout so an active snapshot can
finish on shutdown. SIGTERM interrupts the interval wait; it does not cancel an
active snapshot. Retention applies only after a successful snapshot.

## Isolated restore drill (SQLite)

Use the same application revision and Python dependencies as the snapshot.
Run this drill in a separate checkout and an empty temporary data directory;
never point it at production data. The supported SQLite restore command validates
and checks a staged data directory before publishing it:

```sh
python manage.py restore SNAPSHOT_DIRECTORY --output /srv/openiq-restored
```

It refuses existing destinations unless `--overwrite` is explicit and refuses
to replace the command's own `OPENIQ_DATA_DIR`. Run from an isolated configuration
with all destination services stopped. Overwrite retains the old directory as
`DESTINATION.previous-ID`; a failed final rename restores it automatically. After
a process or host crash between the two renames, inspect that retained directory
before restarting services. Never remove it until the restored data is accepted.

1. Select a completed `openiq-backup-*` directory. Validate its manifest and
   both digests before copying anything. In Python, with `snapshot` set to its
   absolute path:

   ```python
   import hashlib, json, sqlite3
   from pathlib import Path
   snapshot = Path('/srv/openiq-backups/openiq-backup-REPLACE_WITH_TIMESTAMP')
   manifest = json.loads((snapshot / 'manifest.json').read_text())
   assert manifest['format'] == 'openiq-backup-v1'
   assert manifest['engine'] == 'django.db.backends.sqlite3'
   assert set(manifest['sha256']) == {'db.sqlite3', '.secret-key'}
   for name, digest in manifest['sha256'].items():
       assert hashlib.sha256((snapshot / name).read_bytes()).hexdigest() == digest
   with sqlite3.connect((snapshot / 'db.sqlite3').as_uri() + '?mode=ro', uri=True) as db:
       assert db.execute('PRAGMA integrity_check').fetchall() == [('ok',)]
   ```

2. Create a new private drill directory. Copy only `db.sqlite3` and `.secret-key`
   into it, keeping files private (0600 on Linux). Do not copy a live database's
   WAL/SHM files. Set `OPENIQ_DATA_DIR` to this new absolute directory,
   `DATABASE_BACKEND=sqlite`, `ALLOW_LOCAL_LOGIN=1`, and `DEBUG=1`. Unset
   `DATABASE_PATH` and `SECRET_KEY` so the restored files are used. Leave external
   credentials unset and set `ENABLE_DISCORD_DELIVERY=0`.
3. Run `python manage.py check` and `python manage.py migrate --check`. A missing
   migration means the checkout and snapshot differ; investigate before changing
   the restored copy. Start `python manage.py runserver 127.0.0.1:8766`, access
   `/admin/` with the recovery account stored in that snapshot, and confirm known
   guilds, roster entries and finalized wars. If needed, run `bootstrap_admin`
   with `ENABLE_BACKEND_ADMIN=1` against this isolated copy to rotate its password.
4. Stop the drill server. Record snapshot timestamp, application revision,
   checksum/integrity results and inspected records. Remove the temporary copy
   when finished. Production services and their data volume remain running
   throughout this drill.

Scheduler behavior is tested offline. The host permissions, actual container
shutdown and this operator drill still require the LIVE-03 hosting rehearsal.
