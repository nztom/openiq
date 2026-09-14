import sqlite3,subprocess,sys,tempfile
from contextlib import closing
from pathlib import Path
from django.test import SimpleTestCase


class ProcessRecoveryTests(SimpleTestCase):
    def test_sqlite_rolls_back_an_abruptly_terminated_writer(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'recovery.sqlite3'
            with closing(sqlite3.connect(path)) as db:db.execute('CREATE TABLE example(value TEXT)');db.commit()
            script="import sqlite3,sys,os; db=sqlite3.connect(sys.argv[1]); db.execute('BEGIN IMMEDIATE'); db.execute(\"INSERT INTO example VALUES ('uncommitted')\"); os._exit(17)"
            result=subprocess.run([sys.executable,'-c',script,str(path)],capture_output=True,timeout=20)
            self.assertEqual(result.returncode,17)
            with closing(sqlite3.connect(path)) as db:
                self.assertEqual(db.execute('SELECT * FROM example').fetchall(),[])
                self.assertEqual(db.execute('PRAGMA integrity_check').fetchall(),[('ok',)])
