import json,tempfile
from pathlib import Path
from unittest.mock import Mock,patch
import httpx
from django.test import TestCase
from django.contrib.auth.models import User
from .models import Guild,Access,Record
from .capture_api import pair
from .services import execute
from .modules.core import get
from scripts.forward_capture import forward


class CaptureApiTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user('capture')
        self.g=Guild.objects.create(name='Capture')
        Access.objects.create(guild=self.g,user=self.user,role='owner')
        self.session=execute(self.user,self.g.pk,'live','start',{'title':'Battle'})['id']
        self.token=pair(self.user,self.g,self.session)
        self.url=f'/capture/{self.g.pk}/{self.session}/'
        self.event={'id':'one','at':'2026-09-12T10:00:00Z','kind':'kill','player':'Alpha','target':'Beta'}

    def post(self,events=None,token=None):
        return self.client.post(self.url,json.dumps({'events':events if events is not None else [self.event]}),content_type='application/json',HTTP_AUTHORIZATION='Bearer '+(token or self.token))

    def test_replay_deduplication_bounded_diagnostics_and_rotation(self):
        self.assertEqual(self.post().json()['added'],1)
        for _ in range(51):self.assertEqual(self.post().json()['added'],0)
        data=get(self.g,'session',self.session).data
        self.assertEqual(len(data['events']),1);self.assertEqual(len(data['capture_diagnostics']),50)
        self.assertIn('capture_last_seen',data)
        pair(self.user,self.g,self.session)
        self.assertEqual(self.post().status_code,401)

    def test_scope_revocation_and_batch_atomicity(self):
        self.assertEqual(self.post(token='wrong').status_code,401)
        other=Guild.objects.create(name='Other')
        self.assertEqual(self.client.post(f'/capture/{other.pk}/{self.session}/',HTTP_AUTHORIZATION='Bearer '+self.token).status_code,401)
        self.assertEqual(self.post([self.event,{'id':'bad'}]).status_code,400)
        self.assertEqual(get(self.g,'session',self.session).data['events'],[])
        Access.objects.filter(user=self.user).delete()
        self.assertEqual(self.post().status_code,403)

    def test_inactive_issuer_cannot_ingest_until_reactivated(self):
        self.user.is_active=False;self.user.save()
        self.assertEqual(self.post().status_code,403)
        data=get(self.g,'session',self.session).data
        self.assertEqual(data['events'],[]);self.assertNotIn('capture_diagnostics',data)
        self.user.is_active=True;self.user.save()
        self.assertEqual(self.post().status_code,200)

    def test_forwarder_retries_same_batch_then_replays_after_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'events.jsonl';path.write_text(json.dumps(self.event)+'\n')
            response=Mock(status_code=200);response.json.return_value={'ok':True}
            with patch('scripts.forward_capture.httpx.Client') as factory,patch('scripts.forward_capture.time.sleep'):
                client=factory.return_value.__enter__.return_value
                client.post.side_effect=[httpx.ReadTimeout('lost'),response,response]
                forward(path,'https://example.test/capture/','secret',once=True)
                forward(path,'https://example.test/capture/','secret',once=True)
                self.assertEqual(client.post.call_count,3)
                self.assertEqual(client.post.call_args_list[0].kwargs['json'],client.post.call_args_list[2].kwargs['json'])
            with self.assertRaises(ValueError):forward(path,'http://example.test/','secret',once=True)
