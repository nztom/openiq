import os
from contextlib import ExitStack, closing
import hashlib
import io
import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command, CommandError
from django.test import SimpleTestCase, override_settings


class BackupTests(SimpleTestCase):
    def test_online_snapshot_permissions_manifest_and_retention(self):
        with tempfile.TemporaryDirectory() as temporary, ExitStack() as resources:
            root = Path(temporary); source = root / 'live.sqlite3'; output = root / 'backups'
            connection = sqlite3.connect(source)
            resources.enter_context(closing(connection))
            connection.execute('PRAGMA journal_mode=WAL')
            connection.execute('CREATE TABLE example (value TEXT)')
            connection.execute("INSERT INTO example VALUES ('committed')"); connection.commit()
            with override_settings(DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': source}}, SECRET_KEY='backup-test-key'):
                output.mkdir(); (output / 'unrelated').mkdir()
                if os.name != 'nt':
                    (output / 'openiq-backup-20000101T000000000000Z').symlink_to(output / 'unrelated', target_is_directory=True)
                for _ in range(2):
                    stdout = io.StringIO(); call_command('backup', output=output, keep=1, stdout=stdout)
                snapshot = Path(stdout.getvalue().strip())
                saved = sqlite3.connect(snapshot / 'db.sqlite3'); resources.enter_context(closing(saved))
                self.assertEqual(saved.execute('SELECT value FROM example').fetchall(), [('committed',)])
                self.assertEqual((snapshot / '.secret-key').read_text(), 'backup-test-key')
                if os.name != 'nt':self.assertEqual(snapshot.stat().st_mode & 0o777, 0o700)
                manifest = json.loads((snapshot / 'manifest.json').read_text())
                for name, digest in manifest['sha256'].items():
                    self.assertEqual(hashlib.sha256((snapshot / name).read_bytes()).hexdigest(), digest)
                    if os.name != 'nt':self.assertEqual((snapshot / name).stat().st_mode & 0o777, 0o600)
                self.assertEqual(len([p for p in output.glob('openiq-backup-*') if not p.is_symlink()]), 1)
                self.assertTrue((output / 'unrelated').exists())
                with patch('config.database.time.monotonic', side_effect=[0, 999]), self.assertRaises(CommandError):
                    call_command('backup', output=output, timeout=1)
                self.assertFalse(list(output.glob('.openiq-backup-*')))
                with patch('config.database.sqlite3.connect') as connect:
                    connect.return_value.execute.return_value.fetchall.return_value = [('corrupt',)]
                    with self.assertRaises(CommandError):call_command('backup', output=output)

    def test_rejects_missing_database_and_invalid_limits(self):
        with self.assertRaises(CommandError):call_command('backup', output=Path('/tmp'), keep=0)
        with override_settings(DATABASES={'default': {'ENGINE':'django.db.backends.sqlite3','NAME':'/does/not/exist'}}):
            with self.assertRaises(CommandError):call_command('backup', output=Path('/tmp'))
