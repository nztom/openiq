"""Regression tests for the production audit's remaining local blockers."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

import httpx
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.core.management import call_command, CommandError
from django.db import connection
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from .models import Guild, Access, Record, Outbox
from .modules.core import Invalid
from .services import execute


class AuditHardeningTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner')
        self.member = User.objects.create_user('member')
        self.guild = Guild.objects.create(name='Audit')
        Access.objects.create(guild=self.guild, user=self.owner, role='owner')
        Access.objects.create(guild=self.guild, user=self.member, role='member')
        self.roster = execute(self.owner, self.guild.pk, 'roster', 'save', {'name': 'Family'})['id']
        execute(self.owner, self.guild.pk, 'roster', 'link', {'member': self.roster, 'user_id': self.member.pk})
        execute(self.owner, self.guild.pk, 'roster', 'note', {'member': self.roster, 'text': 'Private officer note'})

    def test_successful_http_and_discord_actions_hide_notes_without_erasing_them(self):
        self.client.force_login(self.member)
        for module, action, payload in [('roster', 'class', {'member': self.roster, 'class': 'Wizard'}),
                                       ('integrations', 'twitch_link', {'member': self.roster, 'handle': 'family'}),
                                       ('operations', 'welcome_role', {'member': self.roster, 'role': 'Raider'})]:
            result = self.client.post(f'/api/{self.guild.pk}/{module}/{action}/', payload, content_type='application/json')
            self.assertEqual(result.status_code, 200)
            self.assertNotIn('notes', result.json()['result'])
        for command, arguments in [('class', {'member': self.roster, 'class': 'Witch'}), ('whois', {})]:
            result = execute(self.member, self.guild.pk, 'commands', 'run', {'command': command, 'arguments': arguments})
            self.assertNotIn('Private officer note', json.dumps(result))
        result = execute(self.owner, self.guild.pk, 'roster', 'class', {'member': self.roster, 'class': 'Wizard'})
        self.assertEqual(result['notes'][0]['text'], 'Private officer note')

    @override_settings(REQUEST_LIMITS_ENABLED=True, REQUEST_LIMITS={'admin_login': 1})
    def test_csrf_valid_admin_password_attempts_are_rate_limited(self):
        client = Client(enforce_csrf_checks=True)
        response = client.get('/admin/login/')
        token = client.cookies['csrftoken'].value
        credentials = {'username': 'unknown', 'password': 'incorrect', 'csrfmiddlewaretoken': token}
        self.assertEqual(client.post('/admin/login/', credentials).status_code, 200)
        response = client.post('/admin/login/', credentials)
        self.assertEqual(response.status_code, 429)
        self.assertIn('Retry-After', response)

    def test_invalid_configuration_is_rejected_atomically(self):
        for config in ({'milestones': None}, {'milestones': [True]}, {'milestones': [0]}, {'milestones': [10000001]},
                       {'milestones': list(range(1, 102))}, {'welcome': {'roles': None}}, {'welcome': {'roles': [1]}},
                       {'welcome': {'roles': ['']}}, {'welcome': {'roles': ['x'*81]}}, {'welcome': {'roles': ['x']*26}},
                       {'sync': {'url': []}}, {'sync': {'url': 'x'*2001}}):
            with self.subTest(config=config), self.assertRaises(Invalid):
                execute(self.owner, self.guild.pk, 'admin', 'settings', {'config': config})
        self.guild.refresh_from_db()
        self.assertEqual(self.guild.config, {})
        execute(self.owner, self.guild.pk, 'admin', 'settings', {'config': {'milestones': [], 'welcome': {'roles': []}, 'sync': {'url': ''}}})

    def test_bad_guild_does_not_prevent_other_jobs_and_delivery(self):
        self.guild.config = {'milestones': None}
        self.guild.save()
        healthy = Guild.objects.create(name='Healthy')
        Access.objects.create(guild=healthy, user=self.owner, role='owner')
        reminder = execute(self.owner, healthy.pk, 'community', 'reminder', {'text': 'Ready', 'at': '2020-01-01T00:00:00Z'})
        with patch('guilds.delivery.send_due', return_value={'sent': 0, 'failed': 0}) as delivery, self.assertRaises(CommandError):
            call_command('tick', stdout=io.StringIO(), stderr=io.StringIO())
        delivery.assert_called_once()
        self.assertEqual(Record.objects.get(guild=healthy, kind='reminder', key=reminder['id']).data['status'], 'previewed')
        self.assertTrue(Outbox.objects.filter(guild=healthy).exists())

    def test_external_result_is_discarded_after_config_or_authority_changes(self):
        for change in ('config', 'revision', 'role', 'remove'):
            Access.objects.update_or_create(guild=self.guild, user=self.owner, defaults={'role': 'owner'})
            def fetch(url):
                if change == 'config':
                    Guild.objects.filter(pk=self.guild.pk).update(config={'capture': {'enabled': False}})
                elif change == 'revision':
                    execute(self.owner, self.guild.pk, 'roster', 'class', {'member': self.roster, 'class': 'New class'})
                elif change == 'role':
                    Access.objects.filter(guild=self.guild, user=self.owner).update(role='admin')
                else:
                    Access.objects.filter(guild=self.guild, user=self.owner).delete()
                return ['Family']
            with self.subTest(change=change), patch('guilds.modules.integrations.fetch_roster', side_effect=fetch):
                with self.assertRaises((Invalid, PermissionDenied)):
                    execute(self.owner, self.guild.pk, 'integrations', 'roster_source', {'url': 'https://www.naeu.playblackdesert.com/Adventure/Guild'})
            self.guild.refresh_from_db()
            self.assertNotIn('sync', self.guild.config)

    def test_unrelated_action_does_not_scan_wars_and_unchanged_war_has_no_revision(self):
        war = execute(self.owner, self.guild.pk, 'wars', 'save', {'participants': [{'member': self.roster, 'kills': 1, 'deaths': 2}]})
        with CaptureQueriesContext(connection) as queries:
            execute(self.owner, self.guild.pk, 'roster', 'class', {'member': self.roster, 'class': 'Wizard'})
        self.assertFalse(any("'war'" in query['sql'] for query in queries.captured_queries))
        execute(self.owner, self.guild.pk, 'wars', 'save', {'id': war['id']})
        self.assertEqual(Record.objects.filter(guild=self.guild, kind='war_revision').count(), 1)

    def test_credential_file_failure_rolls_back_account_and_removes_temporary_file(self):
        for operation in ('json.dump', 'os.replace'):
            with tempfile.TemporaryDirectory() as directory, override_settings(DATA_DIR=Path(directory)), patch.dict(os.environ, {'ENABLE_BACKEND_ADMIN': '1', 'BACKEND_ADMIN_USERNAME': 'private-admin'}):
                with patch('guilds.management.commands.bootstrap_admin.'+operation, side_effect=OSError('storage failed')), self.assertRaises(OSError):
                    call_command('bootstrap_admin', stdout=io.StringIO())
                self.assertFalse(User.objects.filter(username='private-admin').exists())
                self.assertEqual(list(Path(directory).iterdir()), [])

    def test_direct_remote_handlers_require_preparation(self):
        from .modules import commands, integrations, operations
        with self.assertRaises(Invalid):
            commands.dispatch(self.guild, 'sync roster', {}, 'owner', self.owner)
        with self.assertRaises(Invalid):
            integrations.handle(self.guild, 'roster_fetch', {}, 'owner', self.owner)
        self.guild.config = {'sync': {'enabled': True, 'weekday': 0, 'hour': 0, 'timezone': 'UTC', 'url': 'https://example.com'}}
        for sources in (None, {}):
            with self.assertRaises(Invalid):
                operations.handle(self.guild, 'tick', {'at': '2026-09-07T12:00:00Z'}, 'owner', self.owner, sources=sources)

    def test_remote_welcome_receipt_prevents_repeated_delivery(self):
        from .discord_components import process, signed_id
        component = signed_id('welcome', self.guild, self.roster, '200')
        with patch('guilds.discord_welcome.choose', return_value={'delivery': 'Discord'}) as choose:
            self.assertEqual(process(self.owner, component, deliver_roles=True, interaction_id='audit'), {'delivery': 'Discord'})
            self.assertEqual(process(self.owner, component, deliver_roles=True, interaction_id='audit'), {'duplicate': True})
        choose.assert_called_once_with(self.owner, self.guild, self.roster, '200', enabled=True)

    def test_scheduler_skips_guild_without_owner(self):
        Guild.objects.create(name='No owner')
        with patch('guilds.delivery.send_due', return_value={'sent': 0}) as delivery:
            call_command('tick', stdout=io.StringIO())
        delivery.assert_called_once()


class ExternalWriterTests(SimpleTestCase):
    def test_external_actions_leave_file_database_available_to_another_process(self):
        script = r'''
import django,os,sqlite3,subprocess,sys
django.setup()
from unittest.mock import patch
import httpx
from django.core.management import call_command
from django.contrib.auth.models import User
from django.db import connection
from guilds.models import Guild,Access,Record
from guilds.services import execute
from guilds.discord_components import process,signed_id
call_command('migrate',verbosity=0)
user=User.objects.create_user('owner');guild=Guild.objects.create(name='Main',server_id='100');other=Guild.objects.create(name='Other')
Access.objects.create(guild=guild,user=user,role='owner')
member=execute(user,guild.pk,'roster','save',{'name':'Family'})['id']
execute(user,guild.pk,'roster','link',{'member':member,'user_id':user.pk,'discord_id':'300'})
writer="import sqlite3,sys; c=sqlite3.connect(sys.argv[1],timeout=.2); c.execute('UPDATE guilds_guild SET revision=revision+1 WHERE id=?',(sys.argv[2],)); c.commit(); c.close()"
count=0
def remote(url,**kwargs):
    global count
    assert not connection.in_atomic_block, 'HTTP executed inside a transaction'
    done=subprocess.run([sys.executable,'-c',writer,os.environ['DATABASE_PATH'],str(other.pk)],capture_output=True,text=True,timeout=5)
    assert done.returncode==0,done.stderr
    count+=1
    request=httpx.Request('GET',url)
    if 'playblackdesert' in url:return httpx.Response(200,text='<a href="/Adventure/Profile">Family</a>',request=request)
    return httpx.Response(200,json={'data':[],'message':{'content':'Summary'}},request=request)
with patch('httpx.post',side_effect=remote),patch('httpx.get',side_effect=remote),patch('httpx.put',side_effect=remote):
    execute(user,guild.pk,'ai','summary',{'text':'Discussion'})
    execute(user,guild.pk,'commands','run',{'command':'notreadingallthat','arguments':{'text':'Discussion'}})
    execute(user,guild.pk,'integrations','roster_fetch',{'url':'https://www.naeu.playblackdesert.com/Adventure/Guild'})
    execute(user,guild.pk,'integrations','roster_source',{'url':'https://www.naeu.playblackdesert.com/Adventure/Guild'})
    execute(user,guild.pk,'integrations','streams_refresh',{})
    execute(user,guild.pk,'commands','run',{'command':'sync roster'})
    execute(user,guild.pk,'operations','schedule',{'kind':'sync','enabled':True,'weekday':0,'hour':0,'timezone':'UTC'})
    execute(user,guild.pk,'operations','tick',{'at':'2026-09-07T12:00:00Z'})
    execute(user,guild.pk,'commands','run',{'command':'catchup-summaries','arguments':{'at':'2026-09-14T12:00:00Z','days':0}})
    execute(user,guild.pk,'admin','settings',{'config':{'welcome':{'roles':['Raider'],'role_ids':{'Raider':'200'}}}})
    guild.refresh_from_db()
    with patch('guilds.discord_welcome.role_context',return_value=({'200':{'position':1}},2)):
        process(user,signed_id('welcome',guild,member,'200'),deliver_roles=True,interaction_id='10')
        assert process(user,signed_id('welcome',guild,member,'200'),deliver_roles=True,interaction_id='10')=={'duplicate':True}
assert count==9,count
'''
        with tempfile.TemporaryDirectory() as directory:
            environment = {**os.environ, 'DJANGO_SETTINGS_MODULE': 'config.settings', 'DATABASE_BACKEND': 'sqlite',
                           'DATABASE_PATH': str(Path(directory)/'writers.sqlite3'), 'OPENIQ_DATA_DIR': directory, 'SECRET_KEY': 'writer-test',
                           'OLLAMA_MODEL': 'test', 'TWITCH_CLIENT_ID': 'test', 'TWITCH_ACCESS_TOKEN': 'test',
                           'ENABLE_DISCORD_DELIVERY': '1', 'DISCORD_BOT_TOKEN': 'test'}
            result = subprocess.run([sys.executable, '-c', script], cwd=settings.BASE_DIR, env=environment, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
