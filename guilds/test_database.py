import io
import json
import tempfile
from unittest.mock import patch
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command, CommandError
from django.test import SimpleTestCase, override_settings

from config.database import (DatabaseBackend, DatabaseOperationError, SQLiteBackend,
                             PostgreSQLBackend, backend_for_database,
                             database_configuration, get_backend)


class ExampleBackend(DatabaseBackend):
    engine = 'example.engine'
    snapshot_name = 'database.dump'

    def configuration(self, data_dir, env):
        return {'ENGINE': self.engine, 'NAME': 'example'}

    def validate_snapshot(self, database):
        pass

    def snapshot(self, database, destination, timeout):
        destination.write_bytes(b'example snapshot')


class DatabaseBackendTests(SimpleTestCase):
    def test_sqlite_defaults_and_legacy_path(self):
        settings = database_configuration(Path('/data'), {})
        self.assertEqual(settings, {'ENGINE': 'django.db.backends.sqlite3', 'NAME': str(Path('/data')/'db.sqlite3'),
                                    'OPTIONS': {'timeout': 20, 'transaction_mode': 'IMMEDIATE'}})
        self.assertEqual(database_configuration('/data', {'DATABASE_PATH': '/other/db.sqlite3'})['NAME'], '/other/db.sqlite3')
        self.assertIsInstance(backend_for_database(settings), SQLiteBackend)

    def test_postgres_configuration_has_no_sqlite_options(self):
        env = {'DATABASE_BACKEND': 'postgresql', 'DATABASE_NAME': 'guilds', 'DATABASE_USER': 'openiq',
               'DATABASE_PASSWORD': 'private', 'DATABASE_HOST': 'db', 'DATABASE_PORT': '5433', 'DATABASE_SSLMODE': 'verify-full'}
        config = database_configuration('/data', env)
        self.assertEqual(config['ENGINE'], 'django.db.backends.postgresql')
        self.assertEqual(config['HOST'], 'db'); self.assertEqual(config['PORT'], '5433')
        self.assertEqual(config['PASSWORD'], 'private'); self.assertEqual(config['OPTIONS'], {'sslmode':'verify-full'})
        self.assertIsInstance(backend_for_database(config), PostgreSQLBackend)
        self.assertIsInstance(get_backend('postgres'), PostgreSQLBackend)
        with self.assertRaises(ImproperlyConfigured):database_configuration('/data', {'DATABASE_BACKEND':'postgres'})
        with tempfile.TemporaryDirectory() as temporary, override_settings(DATABASES={'default':config}, DATABASE_BACKEND='postgresql'):
            output = Path(temporary) / 'backup'
            with patch('config.database.shutil.which',return_value=None),self.assertRaisesMessage(CommandError, 'pg_dump'):call_command('backup', output=output)
            self.assertFalse(output.exists())

    def test_adapter_extension_and_unsupported_configuration(self):
        adapter = 'guilds.test_database.ExampleBackend'
        config = database_configuration('/data', {'DATABASE_BACKEND':adapter})
        self.assertIsInstance(backend_for_database(config, adapter), ExampleBackend)
        with self.assertRaises(ImproperlyConfigured):get_backend('unknown')
        with self.assertRaises(ImproperlyConfigured):get_backend('pathlib.Path')
        with self.assertRaises(ImproperlyConfigured):backend_for_database(config)
        with self.assertRaises(ImproperlyConfigured):backend_for_database(config, 'sqlite')
        base = DatabaseBackend()
        with self.assertRaises(NotImplementedError):base.configuration('/data', {})
        with self.assertRaises(DatabaseOperationError):base.validate_snapshot(config)
        with self.assertRaises(DatabaseOperationError):base.snapshot(config, Path('/tmp/unused'), 1)
        with tempfile.TemporaryDirectory() as temporary, override_settings(DATABASES={'default':config}, DATABASE_BACKEND=adapter):
            stdout = io.StringIO(); call_command('backup', output=Path(temporary), stdout=stdout)
            snapshot = Path(stdout.getvalue().strip())
            self.assertEqual((snapshot / 'database.dump').read_bytes(), b'example snapshot')
            manifest = json.loads((snapshot / 'manifest.json').read_text())
            self.assertEqual(manifest['engine'], 'example.engine')
            self.assertEqual(set(manifest['sha256']), {'database.dump', '.secret-key'})
