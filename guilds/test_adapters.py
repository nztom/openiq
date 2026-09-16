"""Remote contracts are tested with controlled responses, never live credentials."""
import os,time,io,json
from unittest.mock import Mock,patch
import httpx
from django.test import TestCase
from django.test import override_settings
from django.contrib.auth.models import User
from .models import Guild,Access
from .modules.core import Invalid
from .modules.integrations import fetch_roster,ocr,roster_html
from .discord_auth import synchronize

HTML='<a href="/Adventure/Profile?name=A">Alpha</a><a href="/Adventure/Profile?name=A">Alpha</a>'
class AdapterTests(TestCase):
    def test_recovery_requires_fresh_destination_authority_and_audits_parties(self):
        from .services import execute
        from .models import Record,Audit
        owner=User.objects.create_user('issuer');guild=Guild.objects.create(name='Recovery',server_id='99')
        Access.objects.create(user=owner,guild=guild,role='owner')
        key=execute(owner,guild.pk,'admin','adoption_key',{})['key']
        with self.assertRaises(Invalid):execute(owner,guild.pk,'admin','adopt',{'key':key,'server_id':'100'})
        payload={'guild':guild.pk,'key':key,'server_id':'100'}
        self.client.force_login(owner)
        self.assertEqual(self.client.post('/recover/',payload,content_type='application/json').status_code,403)
        user=User.objects.create_user('discord_789');self.client.force_login(user)
        session=self.client.session;session['discord_tokens']={'access':'test'};session['discord_checked']=time.time();session.save()
        for result in [[],[{'id':'100','permissions':'0'}]]:
            with patch('guilds.discord_auth.synchronize',return_value=result):
                self.assertEqual(self.client.post('/recover/',payload,content_type='application/json').status_code,403)
        with patch('guilds.discord_auth.synchronize',side_effect=httpx.ConnectError('offline')):
            self.assertEqual(self.client.post('/recover/',payload,content_type='application/json').status_code,403)
        self.assertFalse(Record.objects.get(guild=guild,kind='adoption').data['used'])
        with patch('guilds.discord_auth.synchronize',return_value=[{'id':'100','permissions':'32'}]):
            self.assertEqual(self.client.post('/recover/',payload,content_type='application/json').status_code,200)
            self.assertEqual(self.client.post('/recover/',payload,content_type='application/json').status_code,400)
        audit=Audit.objects.get(guild=guild,action='admin.recover')
        self.assertEqual(audit.data,{'issued_by':'issuer','redeemed_by':'discord_789','previous_server':'99','server_id':'100'})
    def test_member_login_is_discord_only_unless_development_override_is_enabled(self):
        with override_settings(ALLOW_LOCAL_LOGIN=False):
            response=self.client.get('/login/')
            self.assertEqual(response.status_code,200)
            self.assertContains(response,'Sign in with Discord')
            self.assertContains(response,'View OpenIQ on GitHub')
            self.assertContains(response,'https://github.com/nztom/openiq')
        with override_settings(ALLOW_LOCAL_LOGIN=True):
            response=self.client.get('/login/')
            self.assertEqual(response.status_code,200)
            self.assertContains(response,'Sign in with Discord')
            self.assertContains(response,'View OpenIQ on GitHub')
            self.assertContains(response,'https://github.com/nztom/openiq')

    def test_dashboard_links_to_the_repository(self):
        user=User.objects.create_user('repository-link-owner')
        guild=Guild.objects.create(name='Repository Link Guild')
        Access.objects.create(user=user,guild=guild,role='owner')
        self.client.force_login(user)
        response=self.client.get('/')
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'OpenIQ on GitHub')
        self.assertContains(response,'https://github.com/nztom/openiq')
        self.assertContains(response,'rel="noopener noreferrer"')
    def test_roster_fetch_allowlist_rate_limit_and_empty_page(self):
        response=Mock(status_code=200,text=HTML)
        with patch('httpx.get',return_value=response) as request:
            self.assertEqual(fetch_roster('https://www.naeu.playblackdesert.com/Adventure/Guild'),['Alpha'])
            self.assertFalse(request.call_args.kwargs['follow_redirects'])
            response.status_code=429
            with self.assertRaises(Invalid):fetch_roster('https://www.naeu.playblackdesert.com/Adventure/Guild')
            response.status_code=200;response.text='<html>No roster</html>'
            with self.assertRaises(Invalid):fetch_roster('https://www.naeu.playblackdesert.com/Adventure/Guild')
        for url in ['https://evil.example/','https://user@www.naeu.playblackdesert.com/','https://www.naeu.playblackdesert.com:8080/']:
            with self.subTest(url=url),self.assertRaises(Invalid):fetch_roster(url)
        self.assertEqual(roster_html('<span>Ignored</span>'+HTML),['Alpha'])
    def test_ocr_validation_and_normalization(self):
        from PIL import Image
        data=io.BytesIO();Image.new('RGB',(20,20),'white').save(data,format='PNG')
        with patch('pytesseract.image_to_string',return_value='Alpha') as engine:
            self.assertEqual(ocr(data.getvalue()),'Alpha');self.assertEqual(engine.call_args.args[0].mode,'L')
        with self.assertRaises(Invalid):ocr(b'bad image')
        with self.assertRaises(Invalid):ocr(bytes(10*1024*1024+1))
        with patch('pytesseract.image_to_string',side_effect=RuntimeError('timeout')),self.assertRaises(Invalid):ocr(data.getvalue())
    def test_oauth_begin_success_callback_and_replay_rejection(self):
        token=Mock();token.json.return_value={'access_token':'test','refresh_token':'refresh','expires_in':3600}
        profile=Mock();profile.json.return_value={'id':'123'}
        User.objects.create_user('discord_123',password='must-be-disabled')
        with patch.dict(os.environ,{'DISCORD_CLIENT_ID':'id','DISCORD_CLIENT_SECRET':'secret'}):
            result=self.client.get('/auth/discord/');self.assertEqual(result.status_code,302)
            state=self.client.session['oauth_state']['value']
            guilds=[{'id':'555','name':'Server','owner':True,'permissions':'0'}]
            with patch('httpx.post',return_value=token),patch('httpx.get',return_value=profile),patch('guilds.discord_auth.synchronize',return_value=guilds) as sync:
                response=self.client.get('/auth/discord/callback/',{'state':state,'code':'code'})
                self.assertEqual(response.status_code,302);sync.assert_called_once()
                self.assertFalse(User.objects.get(username='discord_123').has_usable_password())
                self.assertEqual(self.client.session['discord_guilds'],guilds)
            self.assertEqual(self.client.get('/auth/discord/callback/',{'state':state,'code':'code'}).status_code,400)
    def test_oauth_denial_malformed_state_and_logout_cleanup(self):
        session=self.client.session;session['oauth_state']={'value':'test','at':time.time()};session.save()
        response=self.client.get('/auth/discord/callback/',{'state':'test','error':'access_denied'})
        self.assertEqual(response.status_code,400);self.assertContains(response,'authorization was denied',status_code=400)
        session=self.client.session;session['oauth_state']={'value':123,'at':'invalid'};session.save()
        self.assertEqual(self.client.get('/auth/discord/callback/',{'state':'123'}).status_code,400)
        user=User.objects.create_user('discord_logout');self.client.force_login(user)
        session=self.client.session;session['discord_tokens']={'access':'secret','expires':time.time()+3600};session['discord_checked']=time.time();session.save()
        self.assertEqual(self.client.get('/logout/').status_code,405)
        self.assertEqual(self.client.post('/logout/').status_code,302)
        self.assertNotIn('discord_tokens',self.client.session)
    def test_oauth_remote_failure_does_not_authenticate(self):
        session=self.client.session;session['oauth_state']={'value':'test','at':time.time()};session.save()
        with patch('httpx.post',side_effect=httpx.ConnectError('offline')):
            self.assertEqual(self.client.get('/auth/discord/callback/',{'state':'test','code':'code'}).status_code,400)
        self.assertNotIn('_auth_user_id',self.client.session)
    def test_synchronize_grants_and_revokes_roles_atomically(self):
        user=User.objects.create_user('discord_user');g=Guild.objects.create(name='Guild',server_id='123',config={'roles':{'admin':['42']}})
        servers=Mock();servers.json.return_value=[{'id':'123'}]
        member=Mock(status_code=200);member.json.return_value={'roles':['42']}
        client=Mock();client.get.side_effect=[servers,member]
        with patch('httpx.Client') as factory:
            factory.return_value.__enter__.return_value=client;result=synchronize(user,'test')
        self.assertEqual(Access.objects.get(user=user,guild=g).role,'admin')
        self.assertEqual(result,[{'id':'123','name':'','owner':False,'permissions':'0'}])
        servers.json.return_value=[];client.get.side_effect=[servers]
        with patch('httpx.Client') as factory:
            factory.return_value.__enter__.return_value=client;synchronize(user,'test')
        self.assertFalse(Access.objects.filter(user=user,guild=g).exists())
    def test_onboarding_requires_verified_discord_server_authority(self):
        user=User.objects.create_user('discord_456');self.client.force_login(user)
        session=self.client.session;session['discord_tokens']={'access':'test'};session['discord_checked']=time.time()
        session['discord_guilds']=[{'id':'100','name':'Managed','owner':False,'permissions':'32'},{'id':'200','name':'Member','owner':False,'permissions':'0'}];session.save()
        response=self.client.post('/onboard/',data='{"name":"Managed Guild","server_id":"100"}',content_type='application/json')
        self.assertEqual(response.status_code,200);self.assertEqual(Guild.objects.get(name='Managed Guild').server_id,'100')
        for server_id in ['200','300','']:
            with self.subTest(server_id=server_id):
                response=self.client.post('/onboard/',data=json.dumps({'name':'Denied '+(server_id or 'empty'),'server_id':server_id}),content_type='application/json')
                self.assertEqual(response.status_code,403)
        self.client.logout();self.client.force_login(User.objects.create_user('local-user'))
        self.assertEqual(self.client.post('/onboard/',data='{"name":"Local","server_id":"100"}',content_type='application/json').status_code,403)
    def test_discord_server_authority_accepts_owner_and_administrator(self):
        from .discord_auth import can_manage_server
        self.assertTrue(can_manage_server({'owner':True,'permissions':'0'}))
        self.assertTrue(can_manage_server({'owner':False,'permissions':'8'}))
        self.assertFalse(can_manage_server({'owner':False,'permissions':'invalid'}))
    def test_role_refresh_failure_logs_out(self):
        user=User.objects.create_user('discord_user');self.client.force_login(user)
        session=self.client.session;session['discord_tokens']={'access':'test','refresh':'refresh','expires':time.time()+5000};session['discord_checked']=0;session.save()
        with patch('guilds.discord_auth.synchronize',side_effect=httpx.ConnectError('offline')):
            response=self.client.get('/');self.assertEqual(response.status_code,302)
        self.assertNotIn('_auth_user_id',self.client.session)
    def test_expired_token_refresh_success(self):
        user=User.objects.create_user('discord_user');self.client.force_login(user)
        session=self.client.session;session['discord_tokens']={'access':'old','refresh':'refresh','expires':0};session['discord_checked']=0;session.save()
        response=Mock();response.json.return_value={'access_token':'new','expires_in':3600}
        with patch('httpx.post',return_value=response),patch('guilds.discord_auth.synchronize',return_value=[]) as sync:
            self.assertRedirects(self.client.get('/'),'/onboard/',fetch_redirect_response=False);sync.assert_called_once_with(user,'new')
        self.assertEqual(self.client.session['discord_tokens']['access'],'new')
    def test_expired_token_without_refresh_logs_out(self):
        user=User.objects.create_user('discord_expired');self.client.force_login(user)
        session=self.client.session;session['discord_tokens']={'access':'old','expires':0};session['discord_checked']=0;session.save()
        self.assertEqual(self.client.get('/').status_code,302)
        self.assertNotIn('_auth_user_id',self.client.session)
    def test_discord_unconfigured_and_administrator_fallback(self):
        from .discord_auth import role_for
        with patch.dict(os.environ,{'DISCORD_CLIENT_ID':'','DISCORD_CLIENT_SECRET':''}):self.assertEqual(self.client.get('/auth/discord/').status_code,400)
        self.assertEqual(role_for(Guild(name='Blank'),{'permissions':'8'},[]),'owner')
    def test_ocr_headers_and_image_pixel_limit(self):
        from .modules.integrations import paired_scores
        self.assertEqual(paired_scores(['Names\nAlpha','Kills Deaths\n\n10 2'])[0]['kills'],10)
        from unittest.mock import MagicMock
        image=MagicMock(width=5000,height=5000,format='PNG');image.__enter__.return_value=image
        with patch('PIL.Image.open',return_value=image),self.assertRaises(Invalid):ocr(b'image')
