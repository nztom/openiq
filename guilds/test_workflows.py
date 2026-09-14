"""Behavioral regression tests for complete module workflows and failure paths."""
import os
from unittest.mock import Mock,patch
import httpx
from django.test import TestCase,override_settings
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from .models import Guild,Access,Record,Outbox
from .services import execute
from .modules.core import Invalid,get

class WorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner=User.objects.create_user('owner')
        cls.member=User.objects.create_user('member')
        cls.g=Guild.objects.create(name='Test')
        Access.objects.create(guild=cls.g,user=cls.owner,role='owner')
        Access.objects.create(guild=cls.g,user=cls.member,role='member')
    def act(self,module,action,data=None,user=None):
        return execute(user or self.owner,self.g.pk,module,action,data or {})
    def roster(self,name='Alpha'):
        return self.act('roster','save',{'name':name,'joined':'2020-01-01'})['id']
    def event(self,**data):
        return self.act('events','save',{'title':'War','at':'2026-09-01T20:00:00Z','teams':[{'name':'Front','capacity':1}],**data})
    def test_event_templates_reset_archive_and_lock(self):
        e=self.event(archived=True,locked=True)
        t=self.act('events','template',{'event':e['id'],'name':'Preset'})
        new=self.act('events','from_template',{'template':t['id'],'at':'2026-10-01T20:00:00Z'})
        self.assertFalse(new['archived']);self.assertFalse(new['locked']);self.assertEqual(new['signups'],[])
        self.act('events','signup',{'event':new['id'],'member':self.roster(),'team':'Front'})
    def test_event_invalid_teams_and_timezone_are_atomic(self):
        for data in [{'teams':[]},{'teams':[{'name':'A','capacity':1}]*2},{'timezone':'Missing/Zone'}]:
            with self.subTest(data=data),self.assertRaises(Invalid):self.event(**data)
        self.assertEqual(Record.objects.filter(kind='event').count(),0)
    def test_remove_team_requires_moving_signups(self):
        e=self.event();m=self.roster()
        self.act('events','signup',{'event':e['id'],'member':m,'team':'Front'})
        with self.assertRaises(Invalid):self.act('events','save',{'id':e['id'],'teams':[{'name':'Back','capacity':2}]})
        with self.assertRaises(Invalid):self.act('events','signup',{'event':e['id'],'member':m,'team':'Missing'})
        with self.assertRaises(Invalid):self.act('events','next',{'event':e['id']})
        self.assertEqual(get(self.g,'event',e['id']).data['teams'][0]['name'],'Front')
    def test_component_rejects_negative_index_and_unlinked_accounts(self):
        from .discord_components import process
        e=self.event();m=self.roster()
        with self.assertRaises(Invalid):process(self.member,f"signup:{self.g.pk}:{e['id']}:0")
        self.act('roster','link',{'member':m,'user_id':self.member.pk})
        for index in ['-1','999','bad']:
            with self.subTest(index=index),self.assertRaises(Invalid):process(self.member,f"signup:{self.g.pk}:{e['id']}:{index}")
        process(self.member,f"signup:{self.g.pk}:{e['id']}:0")
        process(self.member,f"signup:{self.g.pk}:{e['id']}:withdraw")
        self.assertEqual(get(self.g,'event',e['id']).data['signups'],[])
    def test_roster_review_sync_notes_and_backfill(self):
        m=self.roster();n=self.roster('Beta')
        w=self.act('wars','save',{'date':'2026-09-01','participants':[{'member':m,'kills':4,'deaths':2}]})
        self.act('roster','class',{'member':m,'class':'Shai','spec':'Ascension','backfill':True})
        self.assertEqual(get(self.g,'war',w['id']).data['participants'][0]['class'],'Shai')
        self.act('roster','note',{'member':m,'text':'Initial'})
        self.act('roster','note',{'member':m,'text':'Edited','index':0})
        self.assertEqual(get(self.g,'member',m).data['notes'][0]['text'],'Edited')
        with self.assertRaises(Invalid):self.act('roster','note',{'member':m,'text':'Wrong','index':4})
        result=self.act('roster','sync',{'names':['ALPHA','Gamma']})
        self.assertEqual(result,{'added':1,'inactive':1});self.assertFalse(get(self.g,'member',n).data['active'])
        with self.assertRaises(Invalid):self.roster('alpha')
        self.act('roster','group',{'name':'Front'})
        self.act('roster','remove',{'member':m});self.assertFalse(get(self.g,'member',m).data['active'])
    def test_merge_reconciles_signups_gear_and_assignments(self):
        m=self.roster();n=self.roster('Beta');e=self.event()
        for key in [m,n]:self.act('events','signup',{'event':e['id'],'member':key,'team':'Front'})
        self.act('gear','save',{'member':n,'ap':300,'aap':310,'dp':400})
        lead=self.act('coaching','lead',{'name':'Mentor','capacity':2})
        a=self.act('coaching','assign',{'member':n,'lead':lead['id']})
        self.act('roster','merge',{'source':n,'target':m})
        self.assertEqual(len(get(self.g,'event',e['id']).data['signups']),1)
        self.assertEqual(Record.objects.get(kind='gear').data['member'],m)
        self.assertEqual(get(self.g,'assignment',a['id']).data['member'],m)
    def test_coaching_resolution_notifications_and_windows(self):
        from .modules.coaching import flags,window
        m=self.roster();w=self.act('wars','save',{'date':'2026-09-01','participants':[{'member':m,'kills':0,'deaths':20}]})
        self.act('coaching','settings',{'grace_days':0,'kdr_mode':'all','attendance_mode':'days','no_show_mode':'month'})
        self.g.refresh_from_db();self.assertIn('KDR',flags(self.g)[0]['reasons'])
        lead=self.act('coaching','lead',{'name':'Lead','capacity':2});a=self.act('coaching','assign',{'member':m,'lead':lead['id']})
        self.assertEqual(flags(self.g),[])
        with self.assertRaises(Invalid):self.act('coaching','assign',{'member':m,'lead':lead['id']})
        self.assertIn('mentor Alpha',self.act('coaching','notify',{'assignment':a['id']})['text'])
        self.act('coaching','resolve',{'assignment':a['id'],'outcome':'Improved'});self.assertEqual(flags(self.g),[])
        e=self.event();self.act('coaching','link_event',{'event':e['id'],'war':w['id']})
        self.assertEqual(get(self.g,'event',e['id']).data['war'],w['id'])
        self.assertEqual(window([{'date':'2000-01-01'}],{'mode':'days','size':7}),[])
        self.assertEqual(window([{'date':'2000-01-01'}],{'mode':'month'}),[])
    def test_access_changes_preserve_last_owner(self):
        with self.assertRaises(Invalid):self.act('admin','access',{'username':'owner','role':'member'})
        with self.assertRaises(Invalid):self.act('admin','access',{'username':'missing','role':'owner'})
        self.act('admin','access',{'username':'member','role':'owner'})
        self.act('admin','access',{'username':'owner','role':'admin'})
        self.assertEqual(Access.objects.get(user=self.owner,guild=self.g).role,'admin')
        with self.assertRaises(PermissionDenied):self.act('admin','settings',{'config':{}})
    def test_settings_validation_and_purge(self):
        for config in [[],{'unknown':True}]:
            with self.assertRaises(Invalid):self.act('admin','settings',{'config':config})
        self.act('admin','settings',{'config':{'embed_color':'#ffffff'}})
        m=self.roster();self.act('wars','save',{'date':'2026-09-01','participants':[{'member':m,'kills':1,'deaths':1}]})
        self.act('admin','purge',{'confirmation':'Test'})
        self.assertFalse(Record.objects.filter(kind='war').exists());self.assertTrue(Record.objects.filter(kind='member').exists())
    def test_ticket_application_and_reminder_ownership(self):
        ticket=self.act('community','ticket',{'subject':'Help','text':'Details'},self.member)
        self.act('community','reply',{'ticket':ticket['id'],'text':'Follow-up'},self.member)
        self.act('community','close_ticket',{'ticket':ticket['id']})
        self.assertEqual(get(self.g,'ticket',ticket['id']).data['status'],'closed')
        app=self.act('community','apply',{'family':'Alpha','answers':'Shai'},self.member)
        self.act('community','review_application',{'application':app['id'],'status':'accepted','review':'Welcome'})
        self.assertEqual(get(self.g,'application',app['id']).data['status'],'accepted')
        r=self.act('community','reminder',{'text':'Remember','at':'2099-01-01T00:00:00Z'},self.member)
        with self.assertRaises(PermissionDenied):self.act('community','cancel_reminder',{'reminder':r['id']})
        self.act('community','cancel_reminder',{'reminder':r['id']},self.member)
        self.assertEqual(get(self.g,'reminder',r['id']).data['status'],'cancelled')
    def test_delivery_send_update_and_failure_preserve_state(self):
        from .delivery import deliver
        item=Outbox.objects.create(guild=self.g,key='test',channel='123',text='Hello')
        with patch.dict(os.environ,{'ENABLE_DISCORD_DELIVERY':'0'}),self.assertRaises(Invalid):deliver(item,True)
        response=Mock();response.json.return_value={'id':'456'}
        with patch.dict(os.environ,{'ENABLE_DISCORD_DELIVERY':'1','DISCORD_BOT_TOKEN':'test'}),patch('httpx.request',return_value=response) as request:
            self.assertEqual(deliver(item,True)['message_id'],'456');self.assertEqual(request.call_args.args[0],'POST')
            deliver(item,True);self.assertEqual(request.call_args.args[0],'PATCH')
            self.assertTrue(request.call_args.args[1].endswith('/456'))
            item.status='preview';item.save();request.side_effect=httpx.ConnectError('offline')
            with self.assertRaises(httpx.ConnectError):deliver(item,True)
            item.refresh_from_db();self.assertEqual(item.status,'retry')
    def test_ai_errors_and_permission(self):
        m=self.roster()
        with patch.dict(os.environ,{'OLLAMA_MODEL':''}):
            self.assertIn('offline',self.act('ai','summary',{'text':'Decision. Action.'},self.member)['mode'])
            self.assertIn('Alpha',self.act('ai','roast',{'member':m})['text'])
            with self.assertRaises(PermissionDenied):self.act('ai','roast',{'member':m},self.member)
        with patch.dict(os.environ,{'OLLAMA_MODEL':'test'}),patch('httpx.post',side_effect=httpx.ConnectError('offline')),self.assertRaises(Invalid):self.act('ai','summary',{'text':'Hello'})
    def test_intelligence_backfill_and_queue(self):
        from .modules.intelligence import extended
        m=self.roster();session=self.act('live','start',{'title':'War'})
        self.act('live','ingest',{'session':session['id'],'events':[{'id':'1','at':'2026-09-01T20:00:00Z','kind':'kill','player':'Alpha','target':'Enemy','guild':'Rival'}]})
        self.act('intelligence','character',{'character':'Enemy','family':'Other','class':'Shai','guild':'Rival'})
        for name in ['Enemy','Missing']:self.act('intelligence','queue_lookup',{'character':name})
        self.assertEqual(self.act('intelligence','resolve_queue')['resolved'],1)
        self.assertEqual(self.act('intelligence','resolve_queue')['resolved'],0)
        result=extended(self.g);self.assertEqual(result['matchups'][m]['Enemy']['kills'],1)
        self.assertEqual(get(self.g,'session',session['id']).data['events'][0]['class'],'Shai')
    def test_read_commands_and_privacy(self):
        from .modules.commands import READ
        m=self.roster();self.act('roster','link',{'member':m,'user_id':self.member.pk})
        self.act('roster','note',{'member':m,'text':'Staff only'})
        w=self.act('wars','save',{'date':'2026-09-01','participants':[{'member':m,'kills':2,'deaths':1}]})
        for command in READ:
            with self.subTest(command=command):
                result=self.act('commands','run',{'command':command,'arguments':{'member':m,'war':w['id']}})
                self.assertIsInstance(result,dict)
        result=self.act('commands','run',{'command':'whois'},self.member)
        self.assertEqual(len(result['members']),1);self.assertNotIn('notes',result['members'][0])
        with self.assertRaises(Invalid):self.act('commands','run',{'command':'reset-class'})
        self.act('commands','run',{'command':'setclass','arguments':{'class':'Shai','spec':'Ascension'}},self.member)
        self.act('commands','run',{'command':'reset-class'},self.member)
        self.assertEqual(get(self.g,'member',m).data['class'],'Unknown')
    def test_command_configuration_and_overrides(self):
        m=self.roster()
        for command in ['exception','removeexception','unlink','unlink-twitch','reset-class','gearping','setbotchannel','setsyncnotifications','seteventlog','configweeklysummary','setup']:
            with self.subTest(command=command):self.act('commands','run',{'command':command,'arguments':{'member':m,'names':['Alpha'],'channel':'123'}})
        self.act('admin','settings',{'config':{'command_permissions':{'guildstats':'owner'}}})
        with self.assertRaises(PermissionDenied):self.act('commands','run',{'command':'guildstats'},self.member)
        with self.assertRaises(Invalid):self.act('commands','run',{'command':'missing'})
    def test_alliance_opt_in_totals_and_leave(self):
        from .modules.alliances import overview
        partner=Guild.objects.create(name='Partner');Access.objects.create(guild=partner,user=self.owner,role='owner')
        a=self.act('alliances','create',{'name':'Together','partners':[partner.pk]})
        execute(self.owner,partner.pk,'alliances','respond',{'alliance':a['id'],'response':'accepted'})
        m=self.roster()
        for included,kills in [(True,10),(False,90)]:self.act('wars','save',{'date':'2026-09-01','alliance_included':included,'participants':[{'member':m,'kills':kills,'deaths':2}]})
        e=self.event();self.act('events','share',{'event':e['id']})
        result=overview(self.g)[0];self.assertEqual(result['kills'],10);self.assertEqual(len(result['history']),1);self.assertEqual(len(result['events']),1)
        with self.assertRaises(Invalid):self.act('alliances','create',{'name':'Duplicate','partners':[partner.pk]})
        self.act('alliances','leave',{'alliance':a['id']});self.assertEqual(overview(self.g)[0]['history'],[])
    def test_stream_fixtures_linking_and_remote_contract(self):
        m=self.roster()
        self.act('integrations','twitch_link',{'member':m,'handle':'player_one'})
        with self.assertRaises(Invalid):self.act('integrations','twitch_link',{'member':m,'handle':'bad name!'})
        self.act('integrations','streams_fixture',{'streams':[{'handle':'player_one','title':'War','viewers':100,'partner':True}]})
        self.assertEqual(get(self.g,'streams','current').data['source'],'fixture')
        with patch.dict(os.environ,{'TWITCH_CLIENT_ID':'','TWITCH_ACCESS_TOKEN':''}),self.assertRaises(Invalid):self.act('integrations','streams_refresh')
        response=Mock(status_code=200);response.json.return_value={'data':[{'user_login':'player_one','title':'War','viewer_count':100,'game_name':'Black Desert'}]}
        users=Mock();users.json.return_value={'data':[{'login':'player_one','broadcaster_type':'partner'}]}
        with patch.dict(os.environ,{'TWITCH_CLIENT_ID':'test','TWITCH_ACCESS_TOKEN':'test'}),patch('httpx.get',side_effect=[response,users]) as request:
            refreshed=self.act('integrations','streams_refresh');self.assertEqual(refreshed['source'],'Twitch');self.assertTrue(refreshed['items'][0]['partner']);self.assertEqual(refreshed['items'][0]['category'],'Black Desert')
            self.assertEqual(request.call_args_list[1].args[0],'https://api.twitch.tv/helix/users')
        rate_limited=Mock(status_code=429)
        with patch.dict(os.environ,{'TWITCH_CLIENT_ID':'test','TWITCH_ACCESS_TOKEN':'test'}),patch('httpx.get',return_value=rate_limited),self.assertRaises(Invalid):self.act('integrations','streams_refresh')
        with patch.dict(os.environ,{'TWITCH_CLIENT_ID':'test','TWITCH_ACCESS_TOKEN':'test'}),patch('httpx.get',side_effect=[response,httpx.HTTPError('profiles unavailable')]):
            self.assertFalse(self.act('integrations','streams_refresh')['items'][0]['partner'])
        empty=Mock(status_code=200);empty.json.return_value={'data':[]}
        with patch.dict(os.environ,{'TWITCH_CLIENT_ID':'test','TWITCH_ACCESS_TOKEN':'test'}),patch('httpx.get',return_value=empty) as request:
            self.assertEqual(self.act('integrations','streams_refresh')['items'],[]);request.assert_called_once()
    def test_scheduled_source_failure_and_recurrence(self):
        self.act('operations','schedule',{'kind':'sync','weekday':0,'hour':0,'timezone':'UTC'})
        self.act('operations','tick',{'at':'2026-08-03T12:00:00Z'})
        self.assertEqual(get(self.g,'job','sync:2026-08-03').data['status'],'needs_roster_source')
        self.g.refresh_from_db();self.g.config['sync']['url']='https://www.naeu.playblackdesert.com/Adventure/Guild';self.g.save()
        with patch('guilds.modules.integrations.fetch_roster',side_effect=Invalid('Rate limited')):self.act('operations','tick',{'at':'2026-08-10T12:00:00Z'})
        self.assertEqual(get(self.g,'job','sync:2026-08-10').data['status'],'source_error')
        with patch('guilds.modules.integrations.fetch_roster',return_value=['Alpha']):self.act('operations','tick',{'at':'2026-08-17T12:00:00Z'})
        self.assertTrue(Record.objects.filter(kind='member').exists())
        e=self.event(recurrence_days=7);self.act('operations','tick',{'at':'2026-09-02T12:00:00Z'})
        self.assertIn('next_event',get(self.g,'event',e['id']).data)
    def test_event_group_style_validation_and_template_roundtrip(self):
        e=self.event(teams=[{'name':'Squad A','capacity':2,'group':'Frontline'},{'name':'Squad B','capacity':3,'group':'Frontline'}],image='https://example.com/banner.png',accent='#123ABC')
        t=self.act('events','template',{'event':e['id'],'name':'Grouped'})
        clone=self.act('events','from_template',{'template':t['id'],'at':'2026-10-01T20:00:00Z'})
        self.assertEqual(clone['teams'][1]['group'],'Frontline');self.assertEqual(clone['accent'],'#123ABC')
        for data in [{'image':'javascript:alert(1)'},{'image':'http://example.com/image.png'},{'accent':'red; display:none'}]:
            with self.subTest(data=data),self.assertRaises(Invalid):self.event(**data)
    def test_api_failure_status_and_revision_rollback(self):
        import json
        self.client.force_login(self.owner);self.g.refresh_from_db();revision=self.g.revision
        for module,action,payload in [('missing','save',{}),('roster','save',[]),('roster','save',{'name':''})]:
            with self.subTest(module=module,payload=payload):
                response=self.client.post(f'/api/{self.g.pk}/{module}/{action}/',data=json.dumps(payload),content_type='application/json')
                self.assertEqual(response.status_code,400)
        self.g.refresh_from_db();self.assertEqual(self.g.revision,revision)
        self.client.force_login(self.member)
        self.assertEqual(self.client.post(f'/api/{self.g.pk}/wars/save/',data='{}',content_type='application/json').status_code,403)
    def test_ocr_review_endpoint_and_member_scope(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(f'/ocr/{self.g.pk}/').status_code,400)
        def image():return SimpleUploadedFile('scores.png',b'image',content_type='image/png')
        self.roster()
        with patch('guilds.modules.integrations.ocr',side_effect=['Alpha','10 2']):
            response=self.client.post(f'/ocr/{self.g.pk}/',{'images':[image(),image()]})
            self.assertEqual(response.status_code,200);self.assertIn('draft',response.json())
        with patch('guilds.modules.integrations.ocr',return_value='ambiguous'):
            response=self.client.post(f'/ocr/{self.g.pk}/',{'images':[image()]})
            self.assertIn('review_error',response.json())
        self.client.force_login(self.member)
        self.assertEqual(self.client.post(f'/ocr/{self.g.pk}/',{'images':[image()]}).status_code,403)
        with patch('guilds.modules.integrations.ocr',return_value='AP 300 AAP 310 DP 400'):
            response=self.client.post(f'/ocr/{self.g.pk}/',{'mode':'gear','images':[image()]})
            self.assertEqual(response.json()['gear']['dp'],400)
    def test_health_reports_database_failure(self):
        from django.db import DatabaseError
        self.assertEqual(self.client.get('/healthz/').status_code,200)
        with patch('guilds.health.connection.cursor',side_effect=DatabaseError()):self.assertEqual(self.client.get('/readyz/').status_code,503)
    def test_live_log_link_and_war_deletion_clear_related_references(self):
        m=self.roster();s=self.act('live','start',{'title':'Fight'})
        result=self.act('live','import_log',{'session':s['id'],'text':'[01:00:00] Alpha has killed Enemy from Rival','date':'2026-09-01'})
        self.assertEqual(result['added'],1)
        w=self.act('wars','save',{'date':'2026-09-01','participants':[{'member':m,'kills':1,'deaths':0}]})
        e=self.event();self.act('coaching','link_event',{'event':e['id'],'war':w['id']});self.act('live','link',{'session':s['id'],'war':w['id']})
        self.act('wars','delete',{'war':w['id']})
        self.assertNotIn('war',get(self.g,'event',e['id']).data);self.assertNotIn('war',get(self.g,'session',s['id']).data)
    def test_live_relink_and_deleted_review_lifecycle(self):
        m=self.roster();first=self.act('wars','save',{'participants':[{'member':m,'kills':1,'deaths':1}]});draft=self.act('wars','review',{'rows':[{'name':'Alpha','kills':2,'deaths':1}]})
        second=self.act('wars','finalize',{'import':draft['id'],'participants':[{'member':m,'kills':2,'deaths':1}]})
        old_session=self.act('live','start',{'title':'Old'});new_session=self.act('live','start',{'title':'New'})
        self.act('live','link',{'session':old_session['id'],'war':first['id']});self.act('live','link',{'session':old_session['id'],'war':second['id']});self.assertNotIn('session',get(self.g,'war',first['id']).data)
        self.act('live','link',{'session':new_session['id'],'war':second['id']});self.assertNotIn('war',get(self.g,'session',old_session['id']).data)
        self.act('wars','delete',{'war':second['id']});deleted=get(self.g,'import',draft['id']).data
        self.assertEqual(deleted['status'],'war_deleted');self.assertEqual(deleted['deleted_war'],second['id']);self.assertNotIn('war',get(self.g,'session',new_session['id']).data)
    def test_gear_rival_rankings_and_latest_record(self):
        from .modules.gear import rankings,current
        m=self.roster()
        for ap in [300,310]:self.act('gear','save',{'member':m,'ap':ap,'aap':300,'dp':400})
        self.act('gear','rival',{'name':'Rival','average_score':720,'members':10})
        self.assertEqual(current(self.g)[0]['score'],710);self.assertEqual(rankings(self.g)[0]['name'],'Rival')
    def test_local_fun_success_failure_and_summary(self):
        m=self.roster()
        for roll,success in [(0,True),(1,False)]:
            with patch('random.SystemRandom.random',return_value=roll):self.assertEqual(self.act('community','tap',user=self.member)['success'],success)
        self.assertEqual(self.act('community','summary_text',{'text':'First. Second.'})['summary'],'First. Second.')
        self.assertIn('Alpha',self.act('community','roast',{'member':m})['text'])
        self.act('community','welcome',{'name':'Alpha'})
        self.act('community','weekly')
        e=self.event();self.assertIn('Alpha',self.act('community','ping_missing',{'event':e['id']})['text'])
    def test_review_cancel_and_unknown_action_errors(self):
        draft=self.act('wars','review',{'csv':'name,kills,deaths\nAlpha,1,2'})
        self.assertEqual(self.act('commands','run',{'command':'cancel'})['cancelled'],1)
        with self.assertRaises(Invalid):self.act('wars','finalize',{'import':draft['id']})
        for module in ['roster','wars','events','coaching','alliances','gear','live','intelligence','community','operations','admin','ai','integrations','commands']:
            m=self.roster('Member'+module);s=self.act('live','start',{'title':'Session'})
            with self.subTest(module=module),self.assertRaises(Invalid):self.act(module,'unknown',{'member':m,'session':s['id'],'alliance':'missing'})
    def test_roster_source_preview_and_configured_command_sync(self):
        html='<a href="/Adventure/Profile">Alpha</a>'
        self.assertEqual(self.act('integrations','roster_preview',{'html':html})['names'],['Alpha'])
        with self.assertRaises(Invalid):self.act('integrations','roster_preview',{'html':'No roster'})
        with self.assertRaises(Invalid):self.act('commands','run',{'command':'sync roster'})
        with patch('guilds.modules.integrations.fetch_roster',return_value=['Alpha']):
            self.act('integrations','roster_source',{'url':'https://www.naeu.playblackdesert.com/Adventure/Guild'})
            self.assertTrue(self.act('integrations','roster_fetch',{'url':'https://www.naeu.playblackdesert.com/Adventure/Guild'})['requires_confirmation'])
            self.assertEqual(self.act('commands','run',{'command':'sync roster'})['added'],1)
    @override_settings(ALLOW_LOCAL_LOGIN=True)
    def test_adoption_expiration_and_direct_adopt(self):
        token=self.act('admin','adoption_key')['key']
        with self.assertRaises(Invalid):self.act('admin','adopt',{'key':'wrong','server_id':'123'})
        self.assertEqual(self.act('admin','adopt',{'key':token,'server_id':'123'})['server_id'],'123')
        self.act('admin','adoption_key');record=get(self.g,'adoption','current');record.data['expires']='2000-01-01T00:00:00+00:00';record.save()
        with self.assertRaises(Invalid):self.act('admin','adopt',{'key':token,'server_id':'123'})
    def test_application_form_answers_and_applicant_visibility(self):
        form=self.act('operations','recruitment_form',{'title':'Apply','questions':['Class?','Experience?']})
        payload={'family':'Alpha','answers':'Shai, veteran','form':form['id'],'responses':['Shai','Veteran']}
        own=self.act('community','apply',payload,self.member);self.act('community','apply',payload)
        self.client.force_login(self.member)
        applications=self.client.get(f'/api/{self.g.pk}/state/').json()['records']['application']
        self.assertEqual([a['id'] for a in applications],[own['id']])
        self.assertEqual(applications[0]['responses'],['Shai','Veteran'])
        with self.assertRaises(Invalid):self.act('community','apply',{**payload,'responses':['Shai']},self.member)
        for questions in [[], 'not a list', ['']]:
            with self.subTest(questions=questions),self.assertRaises(Invalid):self.act('operations','recruitment_form',{'title':'Invalid','questions':questions})
    def test_closed_ticket_rejects_replies(self):
        ticket=self.act('community','ticket',{'subject':'Help','text':'Question'},self.member)
        self.act('community','close_ticket',{'ticket':ticket['id']})
        for user in [self.owner,self.member]:
            with self.subTest(user=user.username),self.assertRaises(Invalid):self.act('community','reply',{'ticket':ticket['id'],'text':'Late reply'},user)
        self.assertEqual(get(self.g,'ticket',ticket['id']).data['replies'],[])
    def test_war_review_and_member_merge_edge_cases(self):
        with self.assertRaises(Invalid):self.act('wars','review')
        for payload in [{'rows':[]},{'rows':[{}]*1001}]:
            with self.assertRaises(Invalid):self.act('wars','review',payload)
        m=self.roster();n=self.roster('Beta')
        for participants in [[],[{'member':m,'kills':1,'deaths':1}]*2]:
            with self.assertRaises(Invalid):self.act('wars','save',{'participants':participants})
        w=self.act('wars','save',{'date':'2026-09-01','participants':[{'member':n,'kills':5,'deaths':2}]})
        e=self.event();self.act('events','signup',{'event':e['id'],'member':n,'team':'Front'})
        with self.assertRaises(Invalid):self.act('roster','merge',{'source':m,'target':m})
        self.act('roster','merge',{'source':n,'target':m})
        self.assertEqual(get(self.g,'event',e['id']).data['signups'][0]['member'],m)
        self.assertEqual(get(self.g,'war',w['id']).data['participants'][0]['member'],m)
        from .modules.intelligence import extended
        self.assertEqual(extended(self.g)['awards']['Single-war kills'],'Alpha')
    def test_alliance_invalid_partners_and_busy_partner(self):
        partner=Guild.objects.create(name='Partner');third=Guild.objects.create(name='Third')
        for g in [partner,third]:Access.objects.create(guild=g,user=self.owner,role='owner')
        for partners in [[],[self.g.pk],[999999]]:
            with self.assertRaises(Invalid):self.act('alliances','create',{'name':'Invalid','partners':partners})
        a=execute(self.owner,partner.pk,'alliances','create',{'name':'Busy','partners':[third.pk]})
        with self.assertRaises(Invalid):self.act('alliances','create',{'name':'Conflict','partners':[partner.pk]})
        with self.assertRaises(Invalid):execute(self.owner,partner.pk,'alliances','respond',{'alliance':a['id'],'response':'accepted'})
        with self.assertRaises(Invalid):execute(self.owner,partner.pk,'alliances','unknown',{'alliance':a['id']})
    def test_roster_link_vacation_and_schedule_validation(self):
        m=self.roster();n=self.roster('Beta');self.act('roster','link',{'member':m,'user_id':self.member.pk})
        with self.assertRaises(Invalid):self.act('roster','link',{'member':n,'user_id':self.member.pk})
        with self.assertRaises(Invalid):self.act('roster','vacation',{'member':m,'start':'2026-09-02','end':'2026-09-01'})
        with self.assertRaises(Invalid):self.act('operations','schedule',{'kind':'weekly','timezone':'Bad/Zone'})
        with self.assertRaises(Invalid):self.act('operations','challenge',{'opponent':n})
        with self.assertRaises(Invalid):self.act('operations','challenge',{'opponent':m},self.member)
        s=self.act('live','start',{'title':'War'})
        with self.assertRaises(Invalid):self.act('live','ingest',{'session':s['id'],'events':[{}]*2001})
    @override_settings(ALLOW_LOCAL_LOGIN=True)
    def test_access_and_onboarding_denials(self):
        from django.contrib.auth.models import AnonymousUser
        from .services import access
        outsider=User.objects.create_user('outsider')
        for user in [AnonymousUser(),outsider]:
            with self.assertRaises(PermissionDenied):access(user,self.g)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post('/onboard/',data='{"name":"Test"}',content_type='application/json').status_code,400)
    def test_coaching_exemptions_and_disabled_rules(self):
        from .modules.coaching import flags
        from .modules.core import now
        m=self.roster();self.act('roster','save',{'id':m,'exception':True})
        self.assertEqual(flags(self.g),[])
        self.act('roster','save',{'id':m,'exception':False,'joined':now()[:10]});self.assertEqual(flags(self.g),[])
        self.act('roster','save',{'id':m,'joined':'2020-01-01'})
        self.act('roster','vacation',{'member':m,'start':now()[:10],'end':'2099-01-01'});self.assertEqual(flags(self.g),[])
        self.act('coaching','settings',{'enabled':False});self.g.refresh_from_db();self.assertEqual(flags(self.g),[])
    def test_unlinked_setclass_and_future_command_guard(self):
        with self.assertRaises(Invalid):self.act('commands','run',{'command':'setclass','arguments':{'class':'Shai'}})
        with patch('guilds.modules.commands.COMMANDS',['future-command']),self.assertRaises(Invalid):self.act('commands','run',{'command':'future-command'})
    @override_settings(ALLOW_LOCAL_LOGIN=True)
    def test_miscellaneous_read_and_preview_boundaries(self):
        from .delivery import deliver
        from .discord_components import process
        self.assertEqual(str(self.g),'Test')
        with patch.dict(os.environ,{'ENABLE_DISCORD_DELIVERY':'1','DISCORD_BOT_TOKEN':'test'}),self.assertRaises(Invalid):deliver(Outbox.objects.create(guild=self.g,key='bad',channel='preview'),True)
        with self.assertRaises(Invalid):process(self.member,'unknown')
        with self.assertRaises(Invalid):self.act('integrations','streams_fixture',{'streams':{}})
        self.client.force_login(self.member)
        self.assertEqual(self.client.get('/events/shared/00000000-0000-0000-0000-000000000000/').status_code,404)
        self.assertEqual(self.client.post('/recover/',data='{}',content_type='application/json').status_code,400)
        self.act('coaching','lead',{'name':'Private','capacity':1})
        self.assertNotIn('lead',self.client.get(f'/api/{self.g.pk}/state/').json()['records'])
        self.assertEqual(self.client.post('/onboard/',data='{}',content_type='application/json').status_code,400)
    def test_exception_totals_and_unrelated_assignment(self):
        from .modules.analytics import calculate
        from .modules.coaching import flags
        m=self.roster();n=self.roster('Beta');self.act('roster','save',{'id':m,'exception':True})
        self.act('wars','save',{'participants':[{'member':m,'kills':10,'deaths':1},{'member':n,'kills':0,'deaths':10}]})
        self.assertEqual(calculate(self.g)['totals']['kills'],0)
        lead=self.act('coaching','lead',{'name':'Lead','capacity':1});self.act('coaching','assign',{'member':m,'lead':lead['id']})
        self.assertEqual(flags(self.g)[0]['id'],n)
    def test_existing_recurrence_and_disjoint_alliance(self):
        other=Guild.objects.create(name='Other');partner=Guild.objects.create(name='Partner');fourth=Guild.objects.create(name='Fourth')
        Access.objects.create(guild=other,user=self.owner,role='owner')
        execute(self.owner,other.pk,'alliances','create',{'name':'Separate','partners':[partner.pk]})
        self.act('alliances','create',{'name':'Ours','partners':[fourth.pk]})
        e=self.event(recurrence_days=7);self.act('events','next',{'event':e['id']})
        self.act('operations','tick',{'at':'2026-09-02T00:00:00Z'})
        self.assertEqual(Record.objects.filter(kind='event').count(),2)
