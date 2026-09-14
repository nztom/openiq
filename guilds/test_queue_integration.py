"""Contracts joining the local queue with the readiness PR."""
import io
import json
import os
import subprocess
import sys
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import httpx
from django.conf import settings
from django.core.management import call_command, CommandError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from .delivery import deliver, send_due
from .models import Guild, Outbox, Record
from .modules.community import preview


class QueueIntegrationTests(TestCase):
    def setUp(self):
        self.guild = Guild.objects.create(name='Integration')
        self.item = Outbox.objects.create(guild=self.guild, key='item', channel='123', text='Body')
        environment = patch.dict(os.environ, {'ENABLE_DISCORD_DELIVERY': '1', 'DISCORD_BOT_TOKEN': 'test'})
        environment.start()
        self.addCleanup(environment.stop)

    def response(self, data=None):
        return httpx.Response(200, json=data or {'id': '456'}, request=httpx.Request('GET', 'https://discord.com/test'))

    def test_preview_rows_do_not_consume_delivery_budget(self):
        self.item.delete()
        Outbox.objects.bulk_create([Outbox(guild=self.guild, key=f'draft-{i}', channel='preview', text='Draft') for i in range(150)])
        valid = Outbox.objects.create(guild=self.guild, key='valid', channel='123', text='Send')
        with patch('httpx.request', return_value=self.response()) as request:
            self.assertEqual(send_due(limit=1), {'sent': 1, 'failed': 0})
        request.assert_called_once()
        valid.refresh_from_db()
        self.assertEqual(valid.status, 'sent')

    def test_stale_worker_cannot_resend_or_bypass_backoff_or_cancellation(self):
        for state, retry in [('sent', None), ('failed', None), ('cancelled', None), ('retry', timezone.now()+timedelta(minutes=1))]:
            Outbox.objects.filter(pk=self.item.pk).update(status=state, retry_at=retry)
            with patch('httpx.request') as request:
                self.assertEqual(deliver(self.item, True, queued=True)['status'], state)
                request.assert_not_called()

    def test_claim_fence_preserves_operator_resolution(self):
        def resolved(*args, **kwargs):
            Outbox.objects.filter(pk=self.item.pk).update(status='uncertain', lease_until=None)
            return self.response()
        with patch('httpx.request', side_effect=resolved):
            self.assertEqual(deliver(self.item, True)['status'], 'uncertain')
        self.assertFalse(Record.objects.filter(kind='delivery').exists())

    def test_cancelled_reminder_is_not_revived_by_send_acknowledgement(self):
        self.item.key = f'{self.guild.pk}:reminder:cancelled'
        self.item.save()
        reminder = Record.objects.create(guild=self.guild, kind='reminder', key='cancelled', data={'status': 'cancelled'})
        with patch('httpx.request', return_value=self.response()):
            deliver(self.item, True)
        reminder.refresh_from_db()
        self.assertEqual(reminder.data['status'], 'cancelled')
        reminder.delete()
        with patch('httpx.request', return_value=self.response()):
            self.assertEqual(deliver(self.item, True)['status'], 'sent')

    def test_changed_preview_preserves_claim_and_resets_terminal_retry(self):
        self.item.key = f'{self.guild.pk}:changed'
        self.item.status = 'sending'
        self.item.attempts = 4
        self.item.save()
        preview(self.guild, 'changed', 'New text', '123')
        self.item.refresh_from_db()
        self.assertEqual((self.item.status, self.item.attempts), ('sending', 4))
        self.item.status = 'failed'
        self.item.save()
        preview(self.guild, 'changed', 'Corrected text', '123')
        self.item.refresh_from_db()
        self.assertEqual((self.item.status, self.item.attempts), ('preview', 0))

    def test_reconciliation_rejects_foreign_bot_and_ambiguous_matches(self):
        self.item.status = 'uncertain'
        self.item.save()
        marker = {'footer': {'text': f'OpenIQ delivery {self.guild.pk}:{self.item.pk}'}}
        bot = self.response({'id': 'our-bot'})
        foreign = {'id': '999', 'author': {'id': 'other-bot', 'bot': True}, 'embeds': [marker]}
        with patch('httpx.get', side_effect=[bot, self.response([foreign])]), self.assertRaisesMessage(CommandError, 'unresolved'):
            call_command('reconcile_delivery', self.item.pk, find=True)
        self.assertFalse(Record.objects.filter(kind='delivery').exists())
        own = {**foreign, 'author': {'id': 'our-bot'}}
        with patch('httpx.get', side_effect=[bot, self.response([own, {**own, 'id': '998'}])]), self.assertRaisesMessage(CommandError, 'Multiple matching'):
            call_command('reconcile_delivery', self.item.pk, find=True)

    def test_reconciliation_does_not_overwrite_changed_destination(self):
        self.item.status = 'uncertain'
        self.item.save()
        def remote(*args, **kwargs):
            if '/users/@me' in args[0]:
                return self.response({'id': 'bot'})
            Outbox.objects.filter(pk=self.item.pk).update(channel='789')
            return self.response({'author': {'id': 'bot'}, 'channel_id': '123'})
        with patch('httpx.get', side_effect=remote), self.assertRaisesMessage(CommandError, 'changed during reconciliation'):
            call_command('reconcile_delivery', self.item.pk, message_id='456')
        self.assertFalse(Record.objects.filter(kind='delivery').exists())


class QueueMigrationTests(SimpleTestCase):
    def test_fresh_local_and_pr_upgrade_paths(self):
        script = '''
import django,sys
django.setup()
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
start=sys.argv[1]
executor=MigrationExecutor(connection)
executor.migrate([('guilds',start)])
apps=executor.loader.project_state([('guilds',start)]).apps
Guild=apps.get_model('guilds','Guild');Outbox=apps.get_model('guilds','Outbox');Record=apps.get_model('guilds','Record')
g=Guild.objects.create(name='Upgrade')
item=Outbox.objects.create(guild=g,key='uncertain',channel='123',text='Do not duplicate')
retry=Outbox.objects.create(guild=g,key='retry',channel='123',text='Retry later')
Record.objects.create(guild=g,kind='delivery_pending',key=str(item.pk),data={'channel':'123'})
Record.objects.create(guild=g,kind='delivery_retry',key=str(retry.pk),data={'attempts':2,'next_attempt':2000000000,'lease_until':0})
executor=MigrationExecutor(connection);executor.migrate(executor.loader.graph.leaf_nodes())
from guilds.models import Outbox,RequestLimit
assert Outbox.objects.get(pk=item.pk).status=='uncertain'
assert Outbox.objects.get(pk=retry.pk).status=='retry'
assert Outbox.objects.get(pk=retry.pk).attempts==2
RequestLimit.objects.create(key='works',expires=1)
assert not MigrationExecutor(connection).loader.detect_conflicts()
'''
        for start in ('0001_initial', '0002_requestlimit', '0002_outbox_attempts_outbox_last_error_outbox_lease_until_and_more'):
            with self.subTest(start=start), tempfile.TemporaryDirectory() as directory:
                environment = {**os.environ, 'DJANGO_SETTINGS_MODULE': 'config.settings', 'DATABASE_BACKEND': 'sqlite',
                               'DATABASE_PATH': str(Path(directory)/'migration.sqlite3'), 'OPENIQ_DATA_DIR': directory, 'SECRET_KEY': 'migration-test'}
                result = subprocess.run([sys.executable, '-c', script, start], cwd=settings.BASE_DIR, env=environment,
                                        capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
