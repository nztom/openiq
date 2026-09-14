"""Opt-in real PostgreSQL migration, concurrent mutation, and native restore tests."""
import tempfile,uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from unittest import skipUnless
from django.test import TransactionTestCase
from django.db import connection,connections
from django.contrib.auth.models import User
from .models import Guild,Access,Record
from .services import execute
from config.database import PostgreSQLBackend


@skipUnless(connection.vendor=='postgresql','Requires DATABASE_BACKEND=postgresql')
class PostgreSQLIntegrationTests(TransactionTestCase):
    def test_concurrent_mutations_preserve_both_results(self):
        user=User.objects.create_user('postgres-owner');guild=Guild.objects.create(name='Concurrency')
        Access.objects.create(user=user,guild=guild,role='owner');barrier=Barrier(2)
        def write(name):
            try:
                actor=User.objects.get(pk=user.pk);barrier.wait(timeout=10)
                return execute(actor,guild.pk,'roster','save',{'name':name})
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(write,['Alpha','Beta']))
        self.assertEqual(len(results),2);self.assertEqual(Record.objects.filter(guild=guild,kind='member').count(),2)
        guild.refresh_from_db();self.assertEqual(guild.revision,2)

    def test_native_snapshot_restore_to_separate_database(self):
        import psycopg
        from psycopg import sql
        guild=Guild.objects.create(name='Snapshot')
        database=connection.settings_dict.copy();target='openiq_restore_'+uuid.uuid4().hex[:12]
        credentials={'host':database['HOST'],'port':database['PORT'],'user':database['USER'],'password':database['PASSWORD'],'dbname':'postgres'}
        with psycopg.connect(**credentials,autocommit=True) as admin:
            admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(target)))
            try:
                with tempfile.TemporaryDirectory() as directory:
                    snapshot=Path(directory)/'database.dump';backend=PostgreSQLBackend()
                    backend.snapshot(database,snapshot,30)
                    backend.restore({**database,'NAME':target},snapshot,30)
                    with psycopg.connect(**{**credentials,'dbname':target}) as restored:
                        self.assertEqual(restored.execute('SELECT name FROM guilds_guild WHERE id=%s',(guild.pk,)).fetchone(),('Snapshot',))
            finally:admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(target)))
