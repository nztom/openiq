import hashlib,io,json,sqlite3,tempfile
from pathlib import Path
from contextlib import closing
from unittest.mock import patch
from django.test import SimpleTestCase
from django.core.management import call_command,CommandError


class RestoreTests(SimpleTestCase):
    def snapshot(self,root):
        source=root/'backup';source.mkdir()
        with closing(sqlite3.connect(source/'db.sqlite3')) as db:db.execute('CREATE TABLE example(value TEXT)');db.execute("INSERT INTO example VALUES ('saved')");db.commit()
        (source/'.secret-key').write_text('test-key')
        (source/'manifest.json').write_text(json.dumps({'format':'openiq-backup-v1','sha256':{name:hashlib.sha256((source/name).read_bytes()).hexdigest() for name in ['db.sqlite3','.secret-key']}}))
        return source

    def test_checksum_overwrite_checks_and_atomic_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=self.snapshot(root);target=root/'restored'
            with patch('guilds.management.commands.restore.subprocess.run') as check:
                call_command('restore',str(source),output=target,stdout=io.StringIO())
                self.assertEqual(check.call_count,2)
            self.assertEqual((target/'.secret-key').read_text(),'test-key')
            with self.assertRaises(CommandError):call_command('restore',str(source),output=target)
            import subprocess
            with patch('guilds.management.commands.restore.subprocess.run',side_effect=subprocess.CalledProcessError(1,'check')),self.assertRaises(CommandError):
                call_command('restore',str(source),output=target,overwrite=True)
            self.assertEqual((target/'.secret-key').read_text(),'test-key')
            with patch('guilds.management.commands.restore.subprocess.run'):
                call_command('restore',str(source),output=target,overwrite=True,stdout=io.StringIO())
            self.assertEqual(len(list(root.glob('restored.previous-*'))),1)
            (source/'.secret-key').write_text('tampered')
            with self.assertRaises(CommandError):call_command('restore',str(source),output=root/'bad')
            self.assertFalse((root/'bad').exists())
