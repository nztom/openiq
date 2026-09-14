import io
from datetime import timedelta
from unittest.mock import Mock,patch
import httpx
from django.test import TestCase
from django.core.management import call_command,CommandError
from django.utils import timezone
from .models import Guild,Outbox,Record
from .delivery import deliver,send_due
from .modules.community import preview
from .modules.core import Invalid


class DeliveryQueueTests(TestCase):
    def setUp(self):
        self.g=Guild.objects.create(name='Queue')
        self.item=Outbox.objects.create(guild=self.g,key='queue',channel='123',text='Hello')
        self.env=patch.dict('os.environ',{'ENABLE_DISCORD_DELIVERY':'1','DISCORD_BOT_TOKEN':'test'});self.env.start();self.addCleanup(self.env.stop)

    def response(self,code=200,data=None):
        return httpx.Response(code,json=data or {'id':'456'},request=httpx.Request('POST','https://discord.com/api/v10/test'))

    def test_delivery_claim_updates_and_uncertain_timeout(self):
        def sending(*args,**kwargs):
            self.assertEqual(deliver(self.item,True)['status'],'sending')
            preview(self.g,'changed','Other','preview')
            Outbox.objects.filter(pk=self.item.pk).update(text='Updated while sending')
            return self.response()
        with patch('httpx.request',side_effect=sending) as request:
            self.assertEqual(deliver(self.item,True)['status'],'preview')
            self.assertTrue(request.call_args.kwargs['json']['enforce_nonce'])
        with patch('httpx.request',return_value=self.response()) as request:
            self.assertEqual(send_due()['sent'],1);self.assertEqual(request.call_args.args[0],'PATCH')
        self.item.refresh_from_db();self.assertEqual(self.item.status,'sent')
        self.item.channel='789';self.item.save()
        with patch('httpx.request',side_effect=httpx.ReadTimeout('secret')):
            with self.assertRaises(httpx.ReadTimeout):deliver(self.item,True)
        self.item.refresh_from_db();self.assertEqual(self.item.status,'uncertain');self.assertNotIn('secret',self.item.last_error)
        self.assertEqual(deliver(self.item,True)['status'],'uncertain')

    def test_backoff_terminal_failures_and_expired_leases(self):
        for code,data,status in [(429,{'retry_after':30},'retry'),(429,{'retry_after':'bad'},'retry'),(403,{},'failed'),(500,{},'uncertain')]:
            Outbox.objects.filter(pk=self.item.pk).update(status='preview',attempts=0,retry_at=None)
            with patch('httpx.request',return_value=self.response(code,data)):
                self.assertEqual(send_due()['failed'],1)
            self.item.refresh_from_db();self.assertEqual(self.item.status,status)
        Record.objects.create(guild=self.g,kind='delivery',key=str(self.item.pk),data={'message_id':'456','channel':'123'})
        for response in [self.response(500),httpx.ConnectError('offline')]:
            Outbox.objects.filter(pk=self.item.pk).update(status='preview',retry_at=None)
            with patch('httpx.request',**({'side_effect':response} if isinstance(response,Exception) else {'return_value':response})):
                self.assertEqual(send_due()['failed'],1)
            self.item.refresh_from_db();self.assertEqual(self.item.status,'retry')
        Outbox.objects.filter(pk=self.item.pk).update(status='retry',attempts=5,retry_at=timezone.now()-timedelta(seconds=1))
        with patch('httpx.request',return_value=self.response(429,{'retry_after':1})):send_due()
        self.item.refresh_from_db();self.assertEqual(self.item.status,'failed')
        Outbox.objects.filter(pk=self.item.pk).update(status='sending',lease_until=timezone.now()-timedelta(seconds=1))
        with patch('httpx.request') as request:send_due();request.assert_not_called()
        self.item.refresh_from_db();self.assertEqual(self.item.status,'uncertain')
        with patch.dict('os.environ',{'ENABLE_DISCORD_DELIVERY':'0'}):self.assertEqual(send_due()['sent'],0)

    def test_long_notification_attachment_and_limit(self):
        self.item.text='😀'*2001;self.item.save()
        with patch('httpx.request',return_value=self.response()) as request:deliver(self.item,True)
        self.assertEqual(request.call_args.kwargs['files']['files[0]'][1].decode(),self.item.text)
        self.item.text='x'*(8*1024*1024+1);self.item.save()
        with self.assertRaises(Invalid):deliver(self.item,True)

    def test_reconciliation_verifies_bot_identity(self):
        with self.assertRaises(CommandError):call_command('reconcile_delivery',self.item.pk,confirm_not_sent=True)
        self.item.status='uncertain';self.item.save()
        with self.assertRaises(CommandError):call_command('reconcile_delivery',self.item.pk,message_id='bad')
        with patch.dict('os.environ',{'DISCORD_BOT_TOKEN':''}),self.assertRaises(CommandError):call_command('reconcile_delivery',self.item.pk,message_id='456')
        for author in ['other','bot']:
            with patch('httpx.get',side_effect=[self.response(data={'id':'bot'}),self.response(data={'author':{'id':author},'channel_id':'123'})]):
                if author=='other':
                    with self.assertRaises(CommandError):call_command('reconcile_delivery',self.item.pk,message_id='456')
                else:call_command('reconcile_delivery',self.item.pk,message_id='456',stdout=io.StringIO())
        self.assertEqual(Record.objects.get(kind='delivery').data['message_id'],'456')
        Outbox.objects.filter(pk=self.item.pk).update(status='uncertain')
        call_command('reconcile_delivery',self.item.pk,confirm_not_sent=True,stdout=io.StringIO())
        self.assertFalse(Record.objects.filter(kind='delivery').exists())
