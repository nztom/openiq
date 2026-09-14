# Database backend boundaries

Django models, migrations, QuerySets and transactions are the persistence API.
Guild features should continue using them directly. `config/database.py` contains
the database-specific connection settings and maintenance operations.

`DATABASE_BACKEND=sqlite` is the default and preserves existing data paths and
SQLite IMMEDIATE transactions. `DATABASE_PATH` overrides the database file;
otherwise local runs use `OPENIQ_DATA_DIR/db.sqlite3`, and Compose uses
`/data/db.sqlite3`. All three Compose services receive the same database settings.
No schema migration or data conversion is required for this abstraction.

## Adding a backend

1. Extend `DatabaseBackend`, providing the Django `engine` and a
   `configuration(data_dir, env)` method returning a Django database configuration.
2. Select it using its dotted class path in `DATABASE_BACKEND`, or add a short name
   to `BACKENDS`. Custom code must be installed in the application image.
3. For online backups, provide `snapshot_name`, `validate_snapshot(database)` and
   `snapshot(database, destination, timeout)`. Validation must fail before creating
   any output if the operation is unavailable. Write a consistent standalone
   snapshot to the supplied path and respect the timeout. The shared command
   handles staging, signing-key inclusion, checksums, private permissions,
   publication and retention.
4. Add backend configuration/capability tests and run real database integration
   tests for migrations, JSON fields, uniqueness, concurrent mutations and backups.

The base adapter rejects unsupported backup operations. Snapshot manifests now
include the Django engine; existing SQLite filenames and format remain unchanged.
Future restore code must treat old v1 manifests without an engine as SQLite and
reject incompatible engines rather than assuming every snapshot is a SQLite file.

## PostgreSQL preparation

`DATABASE_BACKEND=postgresql` (alias `postgres`) already builds Django PostgreSQL
settings from `DATABASE_NAME`, `DATABASE_USER`, `DATABASE_PASSWORD`,
`DATABASE_HOST`, `DATABASE_PORT`, and `DATABASE_SSLMODE`. Name and user are required.
SQLite options are never passed to PostgreSQL. Connections default to closing at
the end of a request (`CONN_MAX_AGE=0`).

The driver is locked to psycopg 3.3.5. Native `pg_dump` custom-format snapshots
and transactional `pg_restore` are implemented. Install PostgreSQL client tools
on PATH at least as new as the server; the default Bookworm image includes its
distribution client (PostgreSQL 15). Use a matching client image/package for newer
servers. Server provisioning remains an operator responsibility.

Run the real integration gate with a disposable PostgreSQL database and a role
allowed to create test databases:

```sh
DATABASE_BACKEND=postgresql DATABASE_NAME=openiq_test DATABASE_USER=openiq \
DATABASE_HOST=127.0.0.1 DATABASE_PORT=5432 python manage.py test guilds.test_postgres
```

The tests run Django migrations, concurrent guild mutations, a native snapshot,
and restore to a separate temporary database. PostgreSQL 17.11 on Windows passed
the concurrency and snapshot/restore checks during development. Never point test
credentials at a production role or database.

To restore, stop all application writers, configure a dedicated destination
PostgreSQL database and the snapshot's signing key, then run
`python manage.py restore_postgres SNAPSHOT_DIRECTORY --overwrite`. Checksums
are verified before `pg_restore --single-transaction --clean --if-exists` runs;
Django and migration checks follow. Keep a pre-restore backup. A post-restore
application check failure requires operator investigation before restarting.

## SQLite to PostgreSQL transfer

1. Stop web, scheduler, bot and backup writers. Keep an online SQLite backup and
   its signing key, and keep the original data volume intact for rollback.
2. With the SQLite configuration active, export a private Django fixture:
   `python manage.py dumpdata --natural-foreign --natural-primary --exclude contenttypes --exclude auth.permission --output transfer.json`.
3. Provision an empty PostgreSQL database and dedicated owner role. Set the
   `DATABASE_*` variables listed above and retain the same application signing
   key. Run `python manage.py migrate --noinput`, then
   `python manage.py loaddata transfer.json`.
4. Run `python manage.py check` and `python manage.py migrate --check`. Compare
   guild/member/war counts and inspect representative exports before reopening
   access. Create and restore a PostgreSQL backup into another empty database.
5. Start one writer service at a time. If validation fails, stop all writers and
   return to the original SQLite configuration and unchanged data volume.
   Remove the private transfer fixture only after acceptance and an off-host backup.

Selecting a backend does not automatically move data. After PostgreSQL receives
new writes, rollback to the original SQLite database loses those newer changes;
plan the cutover and acceptance window accordingly.

## Mutation locking

`guilds.services.execute` runs inside `transaction.atomic` and updates the guild
revision before reading mutable domain records. The ORM UPDATE takes SQLite's
writer lock or a PostgreSQL row lock, held to transaction end. Keep that write
before domain reads; replacing it with an unlocked read risks lost updates.
Cross-guild operations still require concurrency review on each new database.

Reference: [Django database backend documentation](https://docs.djangoproject.com/en/5.2/ref/databases/).
