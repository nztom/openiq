"""Operator boundary and failure-recovery regression checks."""
import hashlib,io,json,os,subprocess,tempfile
from pathlib import Path
from unittest.mock import patch
from django.test import SimpleTestCase,TestCase,override_settings
from django.core.management import call_command,CommandError
from django.contrib.auth.models import User
from config.database import PostgreSQLBackend,DatabaseOperationError
from .models import Guild,Access,Record
from .services import execute
from .backup_manifest import validate_snapshot
from .modules.core import Invalid,save,get
from .settings_validation import validate
from . import test_restore


class SnapshotSafetyTests(SimpleTestCase):
    def test_manifest_rejects_wrong_format_missing_files_and_unknown_engine(self):
        with tempfile.TemporaryDirectory() as directory:
            source=test_restore.RestoreTests().snapshot(Path(directory))
            path=source/'manifest.json';original=json.loads(path.read_text())
            for changes in ({'format':'unknown'},{'engine':'unknown'},{'sha256':{'../escape':'x'}},{'sha256':{'.secret-key':'bad','db.sqlite3':'bad'}}):
                path.write_text(json.dumps({**original,**changes}))
                with self.assertRaises(CommandError):validate_snapshot(source)
            path.write_text(json.dumps(original));(source/'db.sqlite3').unlink()
            with self.assertRaises(CommandError):validate_snapshot(source)

    def test_restore_guards_and_publication_rollback(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=test_restore.RestoreTests().snapshot(root);target=root/'restored'
            for options in ({'timeout':0},{'output':source},{'output':root,'overwrite':True}):
                with self.assertRaises(CommandError):call_command('restore',str(source),**{'output':target,**options})
            target.write_text('keep')
            with self.assertRaises(CommandError):call_command('restore',str(source),output=target,overwrite=True)
            target.unlink();target.mkdir();(target/'existing').write_text('keep')
            rename=os.rename
            def fail_stage(src,dst):
                if Path(src).name.startswith('.openiq-restore-'):raise OSError('publication failure')
                return rename(src,dst)
            with patch('guilds.management.commands.restore.subprocess.run'),patch('guilds.management.commands.restore.os.rename',side_effect=fail_stage),self.assertRaises(OSError):
                call_command('restore',str(source),output=target,overwrite=True)
            self.assertEqual((target/'existing').read_text(),'keep')
            with override_settings(DATA_DIR=target),self.assertRaises(CommandError):call_command('restore',str(source),output=target,overwrite=True)
            (source/'db.sqlite3').write_text('not a database')
            manifest=json.loads((source/'manifest.json').read_text());manifest['sha256']['db.sqlite3']=hashlib.sha256((source/'db.sqlite3').read_bytes()).hexdigest();(source/'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaises(CommandError):call_command('restore',str(source),output=target,overwrite=True)
            self.assertEqual((target/'existing').read_text(),'keep')

    def test_postgres_client_failure_never_exposes_password(self):
        backend=PostgreSQLBackend();database={'USER':'operator','NAME':'test','PASSWORD':'do-not-print'}
        with patch('config.database.shutil.which',return_value=None),self.assertRaises(DatabaseOperationError):backend.validate_snapshot(database)
        with patch('config.database.subprocess.run',side_effect=subprocess.CalledProcessError(1,'tool',stderr='do-not-print')) as run:
            with self.assertRaises(DatabaseOperationError) as caught:backend.restore(database,Path('backup'),2)
            self.assertNotIn('do-not-print',str(caught.exception));self.assertNotIn('do-not-print',str(run.call_args.args))
            self.assertEqual(run.call_args.kwargs['env']['PGPASSWORD'],'do-not-print')

    def test_postgres_restore_requires_explicit_destination_and_matching_key(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);database={'ENGINE':'django.db.backends.postgresql','NAME':'restore','USER':'test'}
            with self.assertRaises(CommandError):call_command('restore_postgres',str(root))
            with self.assertRaises(CommandError):call_command('restore_postgres',str(root),overwrite=True,timeout=0)
            with override_settings(DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3'}}),self.assertRaises(CommandError):call_command('restore_postgres',str(root),overwrite=True)
            (root/'database.dump').write_bytes(b'fixture');(root/'.secret-key').write_text('restored-key')
            (root/'manifest.json').write_text(json.dumps({'format':'openiq-backup-v1','engine':'django.db.backends.postgresql','sha256':{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in ('database.dump','.secret-key')}}))
            with self.assertRaises(CommandError):call_command('restore',str(root),output=root/'output')
            with override_settings(DATABASES={'default':database},SECRET_KEY='wrong'),self.assertRaises(CommandError):call_command('restore_postgres',str(root),overwrite=True)
            with override_settings(DATABASES={'default':database},SECRET_KEY='restored-key'):
                with patch('guilds.management.commands.restore_postgres.PostgreSQLBackend.restore',side_effect=DatabaseOperationError('failed')),self.assertRaises(CommandError):call_command('restore_postgres',str(root),overwrite=True)
                with patch('guilds.management.commands.restore_postgres.PostgreSQLBackend.restore') as restore,patch('guilds.management.commands.restore_postgres.call_command') as checks:
                    call_command('restore_postgres',str(root),overwrite=True,stdout=io.StringIO());restore.assert_called_once();self.assertEqual(checks.call_count,2)
                with patch('guilds.management.commands.restore_postgres.validate_snapshot',return_value=({},'db.sqlite3')),self.assertRaises(CommandError):call_command('restore_postgres',str(root),overwrite=True)

    def test_settings_reject_invalid_nested_types_and_unusable_roles(self):
        invalid=[{'channels':[]},{'roles':{'unknown':[]}},{'roles':{'owner':7}},{'roles':{'owner':['100']}},{'welcome':{'role_ids':[]}},{'welcome':{'role_ids':{'':'123'}}},{'welcome':{'role_ids':{'Name':'invalid'}}},{'welcome':{'replace_selection':1}},{'capture':{'enabled':'yes'}},{'capture':{'unknown':True}},{'weekly':{'enabled':'yes'}},{'weekly':{'timezone':'Not/Zone'}},{'weekly':{'channel':'bad'}}]
        for config in invalid:
            with self.subTest(config=config),self.assertRaises(Invalid):validate(config,'100')
        validate({'channels':{'bot':''},'tickets':{'custom':'kept','staff_role':'123'},'roles':{'member':'10'},'welcome':{'role_ids':{'Front':'20'},'replace_selection':True},'weekly':{'channel':'123'}},'100')


class OperatorCommandTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user('operator');self.guild=Guild.objects.create(name='Commands')
        Access.objects.create(user=self.user,guild=self.guild,role='owner')
    def test_pair_revoke_and_private_war_export(self):
        session=execute(self.user,self.guild.pk,'live','start',{'title':'Capture'})
        out=io.StringIO();call_command('pair_capture',guild=self.guild.pk,session=session['id'],user=self.user.username,stdout=out)
        self.assertTrue(out.getvalue().strip());self.assertTrue(Record.objects.filter(kind='capture_token').exists())
        call_command('pair_capture',guild=self.guild.pk,session=session['id'],user=self.user.username,revoke=True,stdout=io.StringIO())
        self.assertFalse(Record.objects.filter(kind='capture_token').exists())
        member=execute(self.user,self.guild.pk,'roster','save',{'name':'Family'})
        war=execute(self.user,self.guild.pk,'wars','save',{'participants':[{'member':member['id'],'kills':3,'deaths':1}]})
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'war.json';call_command('export_war',guild=self.guild.pk,war=war['id'],user=self.user.username,output=path,stdout=io.StringIO())
            self.assertEqual(json.loads(path.read_text())['war']['id'],war['id'])
            with self.assertRaises(FileExistsError):call_command('export_war',guild=self.guild.pk,war=war['id'],user=self.user.username,output=path)
    def test_diagnostics_and_environment_commands_have_failing_exit(self):
        for healthy in (True,False):
            with patch('guilds.management.commands.diagnostics.readiness',return_value={'status':'ok' if healthy else 'unavailable','checks':{'database':healthy}}):
                if healthy:call_command('diagnostics',stdout=io.StringIO())
                else:
                    with self.assertRaises(CommandError):call_command('diagnostics',stdout=io.StringIO())
        with patch('guilds.management.commands.validate_environment.problems',return_value=[]):call_command('validate_environment',stdout=io.StringIO())
        with patch('guilds.management.commands.validate_environment.problems',return_value=['Invalid environment']),self.assertRaises(CommandError):call_command('validate_environment')

    def test_capture_disable_inactive_issuer_and_size_limits(self):
        from .capture_api import pair
        session=execute(self.user,self.guild.pk,'live','start',{'title':'Guarded'})['id']
        token=pair(self.user,self.guild,session);url=f'/capture/{self.guild.pk}/{session}/'
        def post(body='{"events":[]}'):
            return self.client.post(url,body,content_type='application/json',HTTP_AUTHORIZATION='Bearer '+token)
        self.assertEqual(self.client.post(url).status_code,401)
        self.assertEqual(post('x'*(1024*1024+1)).status_code,413)
        self.guild.config={'capture':{'enabled':False}};self.guild.save()
        with self.assertRaises(Invalid):pair(self.user,self.guild,session)
        self.assertEqual(post().status_code,403)
        self.guild.config={};self.guild.save();self.user.is_active=False;self.user.save()
        self.assertEqual(post().status_code,403)
        self.user.is_active=True;self.user.save()
        record=get(self.guild,'session',session);record.data['status']='saved';record.save()
        with self.assertRaises(Invalid):pair(self.user,self.guild,session)
        self.assertEqual(post().status_code,400)

    def test_owner_maintenance_relink_remove_and_delete(self):
        from django.contrib.sessions.backends.db import SessionStore
        def command(operation,**options):return call_command('maintain',operation,guild=self.guild.pk,actor=self.user.username,stdout=io.StringIO(),**options)
        with self.assertRaises(CommandError):command('export')
        with self.assertRaises(CommandError):command('cleanup',days=0)
        target=User.objects.create_user('remove-me');Access.objects.create(user=target,guild=self.guild,role='member')
        member=execute(self.user,self.guild.pk,'roster','save',{'name':'Removed'})
        execute(self.user,self.guild.pk,'roster','link',{'member':member['id'],'user_id':target.pk,'discord_id':'123'})
        save(self.guild,'capture_token',{'user':target.pk,'expires':0},'remove-token')
        save(self.guild,'capture_token',{'user':self.user.pk,'expires':99999999999},'keep-token')
        save(self.guild,'adoption',{'expires':'2999-01-01'},'keep-adoption')
        session=SessionStore();session['_auth_user_id']=str(target.pk);session.save()
        other=SessionStore();other['_auth_user_id']=str(self.user.pk);other.save()
        with self.assertRaises(CommandError):command('relink_discord',username=target.username,member=member['id'],discord_id='bad',apply=True)
        outsider=User.objects.create_user('outsider')
        with self.assertRaises(CommandError):command('relink_discord',username=outsider.username,member=member['id'],discord_id='123',apply=True)
        command('relink_discord',username=target.username,member=member['id'],discord_id='456',apply=True)
        self.assertEqual(get(self.guild,'member',member['id']).data['discord_id'],'456')
        command('remove_user',username=target.username,apply=True)
        self.assertFalse(User.objects.filter(pk=target.pk).exists());self.assertEqual(get(self.guild,'member',member['id']).data['user_id'],'')
        self.assertFalse(Record.objects.filter(key='remove-token').exists());self.assertTrue(Record.objects.filter(key='keep-token').exists())
        command('cleanup',apply=True)
        self.assertTrue(Record.objects.filter(key='keep-adoption').exists())
        command('delete_guild',confirmation=self.guild.name,apply=True)
        self.assertFalse(Guild.objects.filter(pk=self.guild.pk).exists())

    def test_privacy_confirmation_last_owner_unlink_and_scoped_exports(self):
        from .modules import privacy
        member=execute(self.user,self.guild.pk,'roster','save',{'name':'OwnerFamily'})
        execute(self.user,self.guild.pk,'roster','link',{'member':member['id'],'user_id':self.user.pk,'discord_id':'123'})
        save(self.guild,'assignment',{'member':member['id'],'text':'private'},'assignment')
        save(self.guild,'gear',{'member':'other'},'unrelated')
        package=execute(self.user,self.guild.pk,'privacy','export',{'member':member['id']})
        self.assertEqual(package['records'][0]['kind'],'assignment')
        with self.assertRaises(Invalid):execute(self.user,self.guild.pk,'privacy','delete',{'member':member['id'],'confirmation':'wrong'})
        with self.assertRaises(Invalid):execute(self.user,self.guild.pk,'privacy','delete',{'member':member['id'],'confirmation':'OwnerFamily'})
        with self.assertRaises(Invalid):privacy.handle(self.guild,'bad',{'member':member['id']},'owner',self.user)
        execute(self.user,self.guild.pk,'privacy','unlink',{'member':member['id']})
        self.assertEqual(get(self.guild,'member',member['id']).data['discord_id'],'')
        execute(self.user,self.guild.pk,'privacy','anonymize',{'member':member['id'],'confirmation':'OwnerFamily'})
        self.assertTrue(get(self.guild,'member',member['id']).data['anonymized'])

    def test_abuse_proxy_identity_and_storage_failure_fail_closed(self):
        from django.test import RequestFactory
        from django.contrib.auth.models import AnonymousUser
        from django.db import DatabaseError
        from django.http import HttpResponse
        from .rate_limits import RequestBudgets
        from .session_security import login_lifetime
        login_lifetime(None,None,self.user)
        middleware=RequestBudgets(lambda request:HttpResponse('ok'))
        with override_settings(REQUEST_LIMITS_ENABLED=True,TRUST_PROXY_HEADERS=True):
            for forwarded in ('203.0.113.5','invalid'):
                request=RequestFactory().post('/capture/1/session/',HTTP_X_FORWARDED_FOR=forwarded,REMOTE_ADDR='127.0.0.1');request.user=AnonymousUser()
                with patch('guilds.rate_limits.consume',return_value=(True,30)) as consume:
                    self.assertEqual(middleware(request).status_code,200)
                    self.assertEqual(consume.call_args.args[0],'ip:'+('203.0.113.5' if forwarded!='invalid' else '127.0.0.1'))
            with patch('guilds.rate_limits.consume',side_effect=DatabaseError('secret')):
                response=middleware(request);self.assertEqual(response.status_code,503);self.assertNotIn(b'secret',response.content)
        from .health import readiness
        with patch('guilds.health.tempfile.TemporaryFile',side_effect=OSError('read only')):self.assertFalse(readiness()['checks']['storage'])

    def test_disabled_integrations_and_retention_settings_validation(self):
        for config in ({'retention':{'bad':1}},{'retention':{'capture_days':-1}},{'retention':{'capture_days':True}}):
            with self.assertRaises(Invalid):execute(self.user,self.guild.pk,'admin','settings',{'config':config})
        execute(self.user,self.guild.pk,'admin','settings',{'config':{'integrations':{'twitch':False,'ollama':False},'retention':{'capture_days':30}}})
        with self.assertRaises(Invalid):execute(self.user,self.guild.pk,'integrations','streams_refresh',{})
        with self.assertRaises(Invalid):execute(self.user,self.guild.pk,'ai','summary',{})
        self.guild.refresh_from_db();self.guild.config['retention']={'capture_days':-1};self.guild.save()
        with self.assertRaises(CommandError):call_command('retention',guild=self.guild.pk)


class RemoteRecoveryTests(TestCase):
    def setUp(self):
        self.guild=Guild.objects.create(name='Remote',server_id='100')
        self.user=User.objects.create_user('remote-owner');Access.objects.create(user=self.user,guild=self.guild,role='owner')
        self.environment=patch.dict(os.environ,{'ENABLE_DISCORD_DELIVERY':'1','DISCORD_BOT_TOKEN':'test'});self.environment.start();self.addCleanup(self.environment.stop)
    def test_unresolved_delivery_history_and_changed_destination(self):
        from unittest.mock import Mock
        from .models import Outbox
        from .delivery import deliver
        item=Outbox.objects.create(guild=self.guild,key='history',channel='123',text='Body')
        item.status='uncertain';item.save()
        bot=Mock();bot.json.return_value={'id':'bot'}
        response=Mock(status_code=200);response.json.return_value=[]
        with patch('httpx.get',side_effect=[bot,response]),self.assertRaisesMessage(CommandError,'unresolved'):call_command('reconcile_delivery',item.pk,find=True)
        response.json.return_value=[{'id':str(i),'embeds':[]} for i in range(100)]
        with patch('httpx.get',side_effect=[bot]+[response]*100) as request,self.assertRaisesMessage(CommandError,'reconciliation limit'):call_command('reconcile_delivery',item.pk,find=True)
        self.assertEqual(request.call_count,101);self.assertIn('before',request.call_args.kwargs['params'])
        call_command('reconcile_delivery',item.pk,confirm_not_sent=True,stdout=io.StringIO())
        save(self.guild,'delivery',{'channel':'old','message_id':'old-message'},str(item.pk))
        response.json.return_value={'id':'new-message'}
        with patch('httpx.request',return_value=response) as request:deliver(item,True)
        self.assertEqual(request.call_args.args[0],'POST')
        self.assertEqual(Record.objects.get(kind='delivery').data['channel'],'123')
    def test_changed_components_remain_queued_and_invalid_retry_header(self):
        import httpx
        from unittest.mock import Mock
        from .models import Outbox
        from .delivery import deliver
        item=Outbox.objects.create(guild=self.guild,key='changed',channel='123',text='Body')
        save(self.guild,'message_components',{'components':[]},str(item.pk))
        response=Mock(status_code=200);response.json.return_value={'id':'message'}
        def change(*args,**kwargs):
            save(self.guild,'message_components',{'components':[],'embeds':[{'description':'new'}]},str(item.pk));return response
        with patch('httpx.request',side_effect=change):deliver(item,True)
        item.refresh_from_db();self.assertEqual(item.status,'preview')
        response=httpx.Response(429,headers={'Retry-After':'invalid'},request=httpx.Request('PATCH','https://discord.com'))
        with patch('httpx.request',return_value=response),self.assertRaises(httpx.HTTPStatusError):deliver(item,True)
        item.refresh_from_db();self.assertEqual(item.attempts,1)
    def test_role_rejection_and_removed_obsolete_role(self):
        import httpx
        from unittest.mock import Mock
        from .discord_welcome import choose
        self.guild.config={'welcome':{'roles':['Raider'],'role_ids':{'Raider':'200'},'replace_selection':True}};self.guild.save()
        member=execute(self.user,self.guild.pk,'roster','save',{'name':'Roles'})['id']
        execute(self.user,self.guild.pk,'roster','link',{'member':member,'user_id':self.user.pk,'discord_id':'400'})
        save(self.guild,'welcome_delivery',{'roles':['deleted']},member)
        with patch('guilds.discord_welcome.role_context',return_value=({'200':{'position':1}},10)):
            for code in (403,500):
                response=httpx.Response(code,request=httpx.Request('PUT','https://discord.com'))
                with patch('httpx.put',return_value=response),self.assertRaises(Invalid if code==403 else httpx.HTTPStatusError):choose(self.user,self.guild,member,'200',True)
            with patch('httpx.put',return_value=Mock()),patch('httpx.delete') as delete:choose(self.user,self.guild,member,'200',True);delete.assert_not_called()
    def test_diagnostics_bad_token_missing_guild_and_remote_failure(self):
        import httpx
        from unittest.mock import Mock
        with patch('httpx.Client') as factory:
            client=factory.return_value.__enter__.return_value
            client.get.side_effect=httpx.ConnectError('private')
            with self.assertRaises(CommandError):call_command('bot_diagnostics')
            response=Mock();response.json.return_value={'id':'bot'};client.get.side_effect=None;client.get.return_value=response
            with self.assertRaises(CommandError):call_command('bot_diagnostics',guild=999)
            self.guild.server_id='bad';self.guild.save();output=io.StringIO()
            call_command('bot_diagnostics',stdout=output);self.assertIn('error',output.getvalue())
    def test_scheduler_stop_heartbeat_and_batch_bound(self):
        from threading import Event
        from unittest.mock import Mock
        from .models import Outbox
        stopped=Event();stopped.set()
        with patch('guilds.management.commands.tick.execute') as execute_job:call_command('tick',stop_event=stopped,stdout=io.StringIO());execute_job.assert_not_called()
        Outbox.objects.bulk_create([Outbox(guild=self.guild,key='batch-'+str(i),channel='123',text='Body') for i in range(101)])
        # Stop after the guild job, before any queued remote work.
        event=Mock();event.is_set.side_effect=[False,True]
        with patch('guilds.delivery.deliver') as deliver:call_command('tick',stop_event=event,stdout=io.StringIO());deliver.assert_not_called()
        with patch('guilds.delivery.deliver',return_value={'status':'preview'}) as deliver,patch('guilds.health.heartbeat') as heartbeat:
            call_command('tick',stop_event=Event(),stdout=io.StringIO());self.assertEqual(deliver.call_count,100);self.assertTrue(heartbeat.called)
    def test_bot_closes_heartbeat_task_and_reports_offline(self):
        import asyncio
        from asgiref.sync import async_to_sync
        from unittest.mock import AsyncMock
        with patch('discord.Client.run',autospec=True) as connect:call_command('runbot')
        bot=connect.call_args.args[0]
        real_sleep=__import__('asyncio').sleep
        async def fast_sleep(delay):await real_sleep(.001)
        async def lifecycle():
            with patch('guilds.health.heartbeat') as heartbeat,patch('discord.Client.close',new_callable=AsyncMock),patch('guilds.management.commands.runbot.asyncio.sleep',new=fast_sleep):
                bot.heartbeat_task=asyncio.create_task(bot.write_heartbeat())
                # Wait until the worker has run its first heartbeat.
                while heartbeat.call_count<2:await asyncio.sleep(.001)
                await bot.close();self.assertEqual(heartbeat.call_args.args,('bot',False))
                del bot.heartbeat_task;await bot.close()
        async_to_sync(lifecycle)()


class RemainingBoundaryTests(TestCase):
    def test_ocr_request_aggregate_limit_and_budget_exhaustion(self):
        from django.test import RequestFactory
        from django.core.files.uploadedfile import SimpleUploadedFile
        from .views import ocr_view
        user=User.objects.create_user('ocr-budget');guild=Guild.objects.create(name='OCR budget');Access.objects.create(user=user,guild=guild,role='owner')
        request=RequestFactory().post('/ocr/',{'images':SimpleUploadedFile('one.png',b'image')});request.user=user;request.upload_too_large=True
        self.assertEqual(ocr_view(request,guild.pk).status_code,413)
        request=RequestFactory().post('/ocr/',{'images':SimpleUploadedFile('one.png',b'image')});request.user=user
        with patch('time.monotonic',side_effect=[0,46]):self.assertEqual(ocr_view(request,guild.pk).status_code,400)

    def test_retention_noop_and_retained_summary_remain_available(self):
        from datetime import timedelta
        from django.utils import timezone
        from .modules.live import summarize
        guild=Guild.objects.create(name='Retained',config={'retention':{'capture_days':1}})
        record=save(guild,'session',{'status':'saved','events':[],'public':False,'retained_summary':{'kills':4}},'old')
        Record.objects.filter(pk=record.pk).update(created=timezone.now()-timedelta(days=3))
        call_command('retention',guild=guild.pk,apply=True,stdout=io.StringIO())
        record.refresh_from_db();self.assertEqual(summarize(record),{'kills':4})
        guild.config={'retention':{'capture_days':10,'recap_days':10,'summary_days':10}};guild.save()
        call_command('retention',guild=guild.pk,apply=True,stdout=io.StringIO());record.refresh_from_db();self.assertEqual(summarize(record),{'kills':4})

    def test_debug_configuration_and_native_snapshot_invocation(self):
        import runpy
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{'DEBUG':'1','OPENIQ_DATA_DIR':directory,'DATABASE_BACKEND':'sqlite'}):
            result=runpy.run_path(str(Path(__file__).resolve().parents[1]/'config/settings.py'));self.assertTrue(result['DEBUG']);self.assertNotIn('STORAGES',result)
        with patch('config.database.shutil.which',return_value='pg_dump'),patch('config.database.subprocess.run') as run:
            PostgreSQLBackend().snapshot({'NAME':'snapshot','USER':'owner'},Path('snapshot.dump'),10)
            self.assertIn('--format=custom',run.call_args.args[0])

    def test_decoded_image_dimensions_are_checked_before_engine(self):
        from PIL import Image
        from .modules.integrations import ocr
        with Image.new('1',(5000,4001)) as image:
            stream=io.BytesIO();image.save(stream,format='PNG')
        with patch('pytesseract.image_to_string') as engine,self.assertRaisesMessage(Invalid,'megapixels'):ocr(stream.getvalue())
        engine.assert_not_called()

    def test_sqlite_integrity_failure_does_not_publish(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=test_restore.RestoreTests().snapshot(root)
            connection=Mock();connection.execute.return_value.fetchall.return_value=[('corrupt',)]
            with patch('guilds.management.commands.restore.sqlite3.connect',return_value=connection),self.assertRaises(CommandError):call_command('restore',str(source),output=root/'destination')
            self.assertFalse((root/'destination').exists())
