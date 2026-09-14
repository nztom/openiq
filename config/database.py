"""Database-specific configuration and operations; domain queries use Django ORM."""
import sqlite3
import time
import os
import shutil
import subprocess
from contextlib import closing
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string


class DatabaseOperationError(RuntimeError):
    """An unavailable or failed backend maintenance operation."""


class DatabaseBackend:
    engine = ''
    snapshot_name = None

    def configuration(self, data_dir, env):
        raise NotImplementedError('Backend must provide Django connection settings')

    def validate_snapshot(self, database):
        raise DatabaseOperationError('Online snapshots are not implemented for this database backend')

    def snapshot(self, database, destination, timeout):
        raise DatabaseOperationError('Online snapshots are not implemented for this database backend')


class SQLiteBackend(DatabaseBackend):
    engine = 'django.db.backends.sqlite3'
    snapshot_name = 'db.sqlite3'

    def configuration(self, data_dir, env):
        return {'ENGINE': self.engine, 'NAME': env.get('DATABASE_PATH') or str(Path(data_dir) / 'db.sqlite3'),
                'OPTIONS': {'timeout': 20, 'transaction_mode': 'IMMEDIATE'}}

    def validate_snapshot(self, database):
        if not Path(database['NAME']).is_file():
            raise DatabaseOperationError('Backup requires an existing file-backed SQLite database')

    def snapshot(self, database, destination, timeout):
        self.validate_snapshot(database)
        source = Path(database['NAME']).resolve()
        deadline = time.monotonic() + timeout

        def progress(status, remaining, total):
            if time.monotonic() > deadline:
                raise DatabaseOperationError('Backup timed out; no completed snapshot was published')

        with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as live:
            with closing(sqlite3.connect(destination)) as saved:
                live.backup(saved, pages=256, progress=progress)
                if saved.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                    raise DatabaseOperationError('Snapshot failed SQLite integrity validation')


class PostgreSQLBackend(DatabaseBackend):
    """Native PostgreSQL snapshots and transactional restore via its client tools."""
    engine = 'django.db.backends.postgresql'
    snapshot_name = 'database.dump'

    def validate_snapshot(self,database):
        if not shutil.which('pg_dump'):raise DatabaseOperationError('Install pg_dump on PATH to back up PostgreSQL')

    def _run(self,tool,database,arguments,timeout):
        environment=os.environ.copy()
        environment.update(PGPASSWORD=database.get('PASSWORD',''),PGSSLMODE=database.get('OPTIONS',{}).get('sslmode','prefer'))
        command=[tool,'--no-password','--host',database.get('HOST') or 'localhost','--port',str(database.get('PORT') or 5432),
                 '--username',database['USER'],'--dbname',database['NAME'],*arguments]
        try:subprocess.run(command,env=environment,timeout=timeout,check=True,capture_output=True)
        except (OSError,subprocess.SubprocessError):raise DatabaseOperationError('PostgreSQL maintenance failed; verify client version, connection, privileges and timeout') from None

    def snapshot(self,database,destination,timeout):
        self.validate_snapshot(database)
        self._run('pg_dump',database,['--format=custom','--file',str(destination)],timeout)

    def restore(self,database,source,timeout):
        self._run('pg_restore',database,['--single-transaction','--exit-on-error','--clean','--if-exists','--no-owner','--no-privileges',str(source)],timeout)

    def configuration(self, data_dir, env):
        if not env.get('DATABASE_NAME') or not env.get('DATABASE_USER'):
            raise ImproperlyConfigured('PostgreSQL requires DATABASE_NAME and DATABASE_USER')
        return {'ENGINE': self.engine, 'NAME': env['DATABASE_NAME'], 'USER': env['DATABASE_USER'],
                'PASSWORD': env.get('DATABASE_PASSWORD', ''), 'HOST': env.get('DATABASE_HOST', 'localhost'),
                'PORT': env.get('DATABASE_PORT', '5432'), 'CONN_MAX_AGE': 0,
                'OPTIONS': {'sslmode': env.get('DATABASE_SSLMODE', 'prefer')}}


BACKENDS = {'sqlite': SQLiteBackend, 'postgresql': PostgreSQLBackend, 'postgres': PostgreSQLBackend}


def get_backend(name):
    """Built-in name or an operator-supplied dotted adapter class path."""
    factory = BACKENDS.get(name)
    if factory is None:
        try:
            factory = import_string(name)
        except ImportError as exc:
            raise ImproperlyConfigured('Unknown DATABASE_BACKEND; use sqlite, postgresql, or an adapter class path') from exc
    if not isinstance(factory, type) or not issubclass(factory, DatabaseBackend):
        raise ImproperlyConfigured('Database adapter must extend DatabaseBackend')
    return factory()


def database_configuration(data_dir, env):
    return get_backend(env.get('DATABASE_BACKEND') or 'sqlite').configuration(data_dir, env)


def backend_for_database(database, adapter_path=''):
    if adapter_path:
        backend = get_backend(adapter_path)
        if backend.engine != database['ENGINE']:
            raise ImproperlyConfigured('Database adapter does not match the configured Django ENGINE')
        return backend
    for factory in BACKENDS.values():
        if factory.engine == database['ENGINE']:
            return factory()
    raise ImproperlyConfigured('No maintenance adapter registered for the configured Django ENGINE')
