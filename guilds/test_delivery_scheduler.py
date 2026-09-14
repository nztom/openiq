import io
import time
from unittest.mock import Mock,patch
import httpx
from django.test import TestCase
from django.contrib.auth.models import User
from django.core.management import call_command
from .models import Guild,Access,Outbox,Record
from .services import execute
from .delivery import deliver
from .modules.core import save
from django.utils import timezone
from datetime import timedelta


class DeliverySchedulerTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user('officer')
        self.g=Guild.objects.create(name='Delivery',config={'channels':{'bot':'123'}})
        Access.objects.create(guild=self.g,user=self.user,role='owner')
        self.env=patch.dict('os.environ',{'ENABLE_DISCORD_DELIVERY':'1','DISCORD_BOT_TOKEN':'test'})
        self.env.start();self.addCleanup(self.env.stop)

    def tick(self):call_command('tick',stdout=io.StringIO(),stderr=io.StringIO())

    def test_due_reminder_delivered_once_across_ticks(self):
        reminder=execute(self.user,self.g.pk,'community','reminder',{'text':'Ready','at':'2020-01-01T00:00:00Z'})
        response=Mock(status_code=200);response.json.return_value={'id':'456'}
        with patch('httpx.request',return_value=response) as request:
            self.tick();self.tick()
        self.assertEqual(request.call_count,1)
        self.assertEqual(Record.objects.get(kind='reminder',key=reminder['id']).data['status'],'sent')

    def test_rate_limit_survives_restart_and_retries_after_delay(self):
        item=Outbox.objects.create(guild=self.g,key='retry',channel='123',text='Retry')
        response=httpx.Response(429,headers={'Retry-After':'90'},request=httpx.Request('POST','https://discord.com'))
        with patch('httpx.request',return_value=response) as request:
            self.tick();self.tick()
        self.assertEqual(request.call_count,1)
        item.refresh_from_db()
        self.assertEqual(item.status,'retry')
        self.assertGreater(item.retry_at,timezone.now()+timedelta(seconds=80))
        item.retry_at=timezone.now()-timedelta(seconds=1);item.save()
        response=Mock(status_code=200);response.json.return_value={'id':'456'}
        with patch('httpx.request',return_value=response) as request:self.tick()
        self.assertEqual(request.call_count,1)
        item.refresh_from_db();self.assertEqual(item.status,'sent')

    def test_claim_blocks_concurrent_sender_and_expired_claim_recovers(self):
        item=Outbox.objects.create(guild=self.g,key='claim',channel='123',text='Once')
        item.status='sending';item.lease_until=timezone.now()+timedelta(seconds=100);item.save()
        with patch('httpx.request') as request:
            self.assertEqual(deliver(item,True)['status'],'sending');request.assert_not_called()
        item.lease_until=timezone.now()-timedelta(seconds=1);item.save()
        with patch('httpx.request') as request:
            self.assertEqual(deliver(item,True,queued=True)['status'],'uncertain');request.assert_not_called()
        call_command('reconcile_delivery',item.pk,confirm_not_sent=True,stdout=io.StringIO())
        response=Mock(status_code=200);response.json.return_value={'id':'456'}
        with patch('httpx.request',return_value=response) as request:deliver(item,True,queued=True);deliver(item,True,queued=True)
        self.assertEqual(request.call_count,1)

    def test_disabled_delivery_and_cancelled_reminder_do_not_send(self):
        reminder=execute(self.user,self.g.pk,'community','reminder',{'text':'Cancel','at':'2020-01-01T00:00:00Z'})
        with patch.dict('os.environ',{'ENABLE_DISCORD_DELIVERY':'0'}),patch('httpx.request') as request:
            self.tick();request.assert_not_called()
        execute(self.user,self.g.pk,'community','cancel_reminder',{'reminder':reminder['id']})
        with patch('httpx.request') as request:self.tick();request.assert_not_called()
