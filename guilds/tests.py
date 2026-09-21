import json
from datetime import datetime,timedelta,timezone
from django.test import TestCase,Client,override_settings
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from guilds.models import Guild,Access,Record,Outbox
from guilds.services import execute
from guilds.modules.core import Invalid,get
from guilds.modules.analytics import calculate
from guilds.modules.coaching import flags

class DomainTests(TestCase):
    def setUp(self):
        self.owner=User.objects.create_user('owner',password='testing-pass-123')
        self.member=User.objects.create_user('member',password='testing-pass-123')
        self.g=Guild.objects.create(name='Guild')
        Access.objects.create(guild=self.g,user=self.owner,role='owner');Access.objects.create(guild=self.g,user=self.member,role='member')
        self.m=self.run_action('roster','save',{'name':'Alpha','joined':'2020-01-01'})['id']
        self.n=self.run_action('roster','save',{'name':'Beta','joined':'2020-01-01'})['id']
        self.run_action('roster','link',{'member':self.m,'user_id':self.member.pk})
    def run_action(self,m,a,p,user=None,g=None):return execute(user or self.owner,(g or self.g).pk,m,a,p)
    def war(self,**kw): return self.run_action('wars','save',{'date':'2026-08-01','participants':[{'member':self.m,'kills':10,'deaths':2}],**kw})
    def event(self,**kw):return self.run_action('events','save',{'title':'Fight','at':'2026-08-01T20:00:00+12:00','teams':[{'name':'Front','capacity':1}],**kw})
    def test_member_cannot_write_wars(self):
        with self.assertRaises(PermissionDenied):self.run_action('wars','save',{},self.member)
    def test_inactive_accounts_are_denied_and_reactivation_restores_access(self):
        self.owner.is_active=False;self.owner.save()
        self.g.refresh_from_db()
        before=(self.g.revision,Record.objects.count(),Outbox.objects.count())
        with self.assertRaisesMessage(PermissionDenied,'inactive'):self.run_action('commands','run',{'command':'guildstats'})
        with self.assertRaisesMessage(PermissionDenied,'inactive'):self.run_action('community','reminder',{'text':'Denied','at':'2099-01-01T00:00:00Z'})
        self.g.refresh_from_db();self.assertEqual((self.g.revision,Record.objects.count(),Outbox.objects.count()),before)
        self.owner.is_active=True;self.owner.save()
        self.assertEqual(self.run_action('commands','run',{'command':'guildstats'})['wars'],0)
    def test_cross_guild_references_rejected(self):
        other=Guild.objects.create(name='Other');Record.objects.create(guild=other,kind='member',key='foreign',data={'name':'Other'})
        with self.assertRaises(Invalid):self.war(participants=[{'member':'foreign','kills':2,'deaths':1}])
    def test_war_context_survives_partial_edits(self):
        war=self.war(location='Calpheon Castle',opponents='Iron Vow, Moonfall',capped=True,cap='Tier 2 · 550 GS')
        edited=self.run_action('wars','save',{'id':war['id'],'note':'Reviewed','participants':war['participants']})
        self.assertEqual((edited['location'],edited['opponents'],edited['cap']),('Calpheon Castle','Iron Vow, Moonfall','Tier 2 · 550 GS'))
    def test_import_review_and_idempotence(self):
        d=self.run_action('wars','review',{'csv':'name,kills,deaths\nAlpha,10,2\nBeto,8,1'})
        self.assertEqual(d['rows'][0]['member'],self.m);self.assertEqual(d['rows'][1]['member'],'')
        p={'import':d['id'],'date':'2026-08-01','participants':[{'member':self.m,'kills':10,'deaths':2},{'member':self.n,'kills':8,'deaths':1}]}
        self.run_action('wars','finalize',p)
        with self.assertRaises(Invalid):self.run_action('wars','finalize',p)
        self.assertEqual(len(calculate(self.g)['timeline']),1)
    def test_atomic_invalid_import(self):
        d=self.run_action('wars','review',{'csv':'name,kills,deaths\nAlpha,10,2'})
        with self.assertRaises(Invalid):self.run_action('wars','finalize',{'import':d['id'],'participants':[{'member':self.m,'kills':-2,'deaths':1}]})
        self.assertEqual(get(self.g,'import',d['id']).data['status'],'review')
        self.assertFalse(Record.objects.filter(kind='war').exists())
    def test_excluded_war_still_attendance(self):
        self.war(excluded=True)
        result=calculate(self.g);self.assertEqual(result['totals']['kills'],0)
        self.assertEqual(next(m for m in result['members'] if m['id']==self.m)['attendance'],100)
    def test_vacation_and_join_eligibility(self):
        self.run_action('roster','vacation',{'member':self.n,'start':'2026-08-01','end':'2026-08-02'});self.war()
        result=calculate(self.g);self.assertIsNone(next(m for m in result['members'] if m['id']==self.n)['attendance'])
    def test_ratio_uses_sums_and_zero_deaths(self):
        self.war(participants=[{'member':self.m,'kills':10,'deaths':0},{'member':self.n,'kills':2,'deaths':4}])
        self.assertEqual(calculate(self.g)['totals']['kdr'],3)
        self.assertIsNone(next(m for m in calculate(self.g)['members'] if m['id']==self.m)['kdr'])
    def test_waitlist_promotes_on_withdraw(self):
        e=self.event()
        self.run_action('events','signup',{'event':e['id'],'member':self.m,'team':'Front'})
        self.run_action('events','signup',{'event':e['id'],'member':self.n,'team':'Front'})
        self.assertTrue(get(self.g,'event',e['id']).data['signups'][1]['waitlisted'])
        self.run_action('events','signup',{'event':e['id'],'member':self.m,'team':''})
        self.assertFalse(get(self.g,'event',e['id']).data['signups'][0]['waitlisted'])
    def test_locked_event_and_member_ownership(self):
        e=self.event(locked=True)
        with self.assertRaises(Invalid):self.run_action('events','signup',{'event':e['id'],'member':self.m,'team':'Front'})
        with self.assertRaises(PermissionDenied):self.run_action('gear','save',{'member':self.n,'ap':300,'aap':301,'dp':400},self.member)
    def test_gear_delete_preserves_history(self):
        self.run_action('gear','save',{'member':self.m,'ap':300,'aap':301,'dp':400},self.member)
        self.run_action('gear','delete',{'member':self.m},self.member)
        self.assertEqual(Record.objects.filter(kind='gear').count(),1)
        self.assertFalse(Record.objects.get(kind='gear').data['current'])
    def test_lead_capacity(self):
        l=self.run_action('coaching','lead',{'name':'Lead','capacity':1})
        self.run_action('coaching','assign',{'member':self.m,'lead':l['id']})
        with self.assertRaises(Invalid):self.run_action('coaching','assign',{'member':self.n,'lead':l['id']})
    def test_alliance_unanimity_and_decline(self):
        b=Guild.objects.create(name='B');c=Guild.objects.create(name='C')
        for g in [b,c]:Access.objects.create(guild=g,user=self.owner,role='owner')
        a=self.run_action('alliances','create',{'name':'Alliance','partners':[b.pk,c.pk]})
        self.run_action('alliances','respond',{'alliance':a['id'],'response':'accepted'},g=b)
        self.assertEqual(get(self.g,'alliance',a['id']).data['status'],'pending')
        self.run_action('alliances','respond',{'alliance':a['id'],'response':'declined'},g=c)
        self.assertEqual(get(self.g,'alliance',a['id']).data['status'],'disbanded')
    def test_live_dedupe_stop_and_public_recap(self):
        s=self.run_action('live','start',{'title':'Live'})
        p={'session':s['id'],'events':[{'id':'1','at':'2026-08-01T10:00:00Z','kind':'kill','player':'Alpha','target':'Enemy'}]}
        self.assertEqual(self.run_action('live','ingest',p)['added'],1)
        self.assertEqual(self.run_action('live','ingest',p)['added'],0)
        self.run_action('live','stop',{'session':s['id']})
        with self.assertRaises(Invalid):self.run_action('live','ingest',p)
        shared=self.run_action('live','share',{'session':s['id'],'public':True})
        self.assertEqual(self.client.get('/recap/'+shared['share_token']+'/').status_code,200)
        self.run_action('live','share',{'session':s['id'],'public':False})
        self.assertEqual(self.client.get('/recap/'+shared['share_token']+'/').status_code,404)
    def test_ticket_privacy_and_audit(self):
        t=self.run_action('community','ticket',{'subject':'Private','text':'Secret'})
        with self.assertRaises(PermissionDenied):self.run_action('community','reply',{'ticket':t['id'],'text':'Intrude'},self.member)
        self.client.force_login(self.member)
        data=self.client.get(f'/api/{self.g.pk}/state/').json()
        self.assertNotIn('ticket',data['records']);self.assertNotIn('audit',data)
    def test_reminders_exactly_once_preview(self):
        self.run_action('community','reminder',{'text':'Reminder','at':'2020-01-01T00:00:00Z'})
        self.run_action('community','run_due',{});self.run_action('community','run_due',{})
        self.assertEqual(Outbox.objects.count(),1);self.assertEqual(Outbox.objects.first().status,'preview')
    def test_csrf_and_anonymous_write(self):
        c=Client(enforce_csrf_checks=True);c.force_login(self.owner)
        self.assertEqual(c.post(f'/api/{self.g.pk}/roster/save/',data='{}',content_type='application/json').status_code,403)
    def test_merge_preserves_totals(self):
        self.war(participants=[{'member':self.m,'kills':10,'deaths':2},{'member':self.n,'kills':5,'deaths':1}]);self.run_action('roster','merge',{'source':self.n,'target':self.m})
        self.assertEqual(calculate(self.g)['totals']['kills'],15)
    def test_empty_roster_does_not_deactivate(self):
        with self.assertRaises(Invalid):self.run_action('roster','sync',{'names':[]})
        self.assertTrue(get(self.g,'member',self.m).data['active'])
    def test_purge_confirmation(self):
        self.war()
        with self.assertRaises(Invalid):self.run_action('admin','purge',{'confirmation':'wrong'})
        self.assertEqual(Record.objects.filter(kind='war').count(),1)
    def test_pages_render(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get('/').status_code,200)
        self.assertEqual(self.client.get(f'/api/{self.g.pk}/state/').status_code,200)
    def test_paired_ocr_validates_row_alignment(self):
        from guilds.modules.integrations import paired_scores,gear_numbers
        self.assertEqual(paired_scores(['Alpha\nBeta','10 2\n5 1'])[1]['kills'],5)
        with self.assertRaises(Invalid):paired_scores(['Alpha','10 2\n5 1'])
        self.assertEqual(gear_numbers(['AP 301\nAAP 303\nDP 400']),{'ap':301,'aap':303,'dp':400})
    def test_local_command_dispatch(self):
        r=self.run_action('commands','run',{'command':'guildstats'})
        self.assertEqual(r['wars'],0)
        r=self.run_action('commands','run',{'command':'roll'},self.member)
        self.assertTrue(1<=r['roll']<=100)
        with self.assertRaises(PermissionDenied):self.run_action('commands','run',{'command':'unlinked'},self.member)
    def test_schedule_idempotence_and_catchup(self):
        self.run_action('operations','schedule',{'kind':'weekly','weekday':0,'hour':0,'timezone':'UTC','enabled':True})
        self.run_action('operations','tick',{'at':'2026-08-03T10:00:00Z'})
        self.run_action('operations','tick',{'at':'2026-08-03T10:00:00Z'})
        self.assertEqual(Record.objects.filter(kind='job').count(),1)
    def test_oauth_state_rejects_forgery(self):
        self.assertEqual(self.client.get('/auth/discord/callback/?state=forged&code=no').status_code,400)
    def test_discord_role_resolution(self):
        from guilds.discord_auth import role_for
        self.g.config={'roles':{'owner':['100'],'admin':['200'],'member':['300']}}
        self.assertEqual(role_for(self.g,{},['200']),'admin')
        self.assertIsNone(role_for(self.g,{},['999']))
    def test_capture_tail_partial_lines_and_rotation(self):
        import tempfile
        from pathlib import Path
        from guilds.capture import JsonLineTail
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'events.jsonl';p.write_text('{"id":"a"')
            tail=JsonLineTail(p);self.assertEqual(tail.read(),[])
            with p.open('a') as f:f.write('}\n')
            self.assertEqual(tail.read(),[{'id':'a'}]);self.assertEqual(tail.read(),[])
            p.write_text('{}\n');self.assertEqual(len(tail.read()),1)
    @override_settings(ALLOW_LOCAL_LOGIN=True)
    def test_onboard_is_private(self):
        self.client.force_login(self.member)
        response=self.client.post('/onboard/',data=json.dumps({'name':'New guild','names':['Fresh']}),content_type='application/json')
        self.assertEqual(response.status_code,200)
        self.assertTrue(Access.objects.filter(guild_id=response.json()['id'],user=self.member,role='owner').exists())
    def test_welcome_recruitment_and_character_modules(self):
        form=self.run_action('operations','recruitment_form',{'title':'Apply','questions':['Class?']})
        self.assertEqual(form['questions'],['Class?'])
        self.run_action('operations','ticket_category',{'name':'Support'})
        self.run_action('operations','welcome_role',{'member':self.m,'role':'Raider'})
        self.assertIn('Raider',get(self.g,'member',self.m).data['community_roles'])
        self.run_action('intelligence','character',{'character':'Enemy','family':'EnemyFamily','class':'Shai','guild':'Opposition'})
    def test_delivery_default_never_uses_network(self):
        from unittest.mock import patch
        from guilds.delivery import deliver
        item=Outbox.objects.create(guild=self.g,key='preview',text='Hello')
        with patch('httpx.request') as network:
            self.assertEqual(deliver(item)['status'],'preview');network.assert_not_called()
    def test_ocr_narrow_columns_fail_for_review(self):
        from guilds.modules.integrations import paired_scores
        with self.assertRaises(Invalid):paired_scores(['Alpha','427'])
    def test_ikusa_contract_midnight_and_death_orientation(self):
        from guilds.modules.logformat import parse_log
        events=parse_log('[23:59:58] Alpha has killed Enemy from Rival (AlphaFamily, EnemyFamily)\n[00:00:02] Alpha died to Enemy from Rival','2026-08-01','+12:00')
        self.assertEqual(events[0]['family'],'EnemyFamily')
        self.assertEqual(events[1]['player'],'Enemy');self.assertEqual(events[1]['target'],'Alpha')
        self.assertEqual((datetime.fromisoformat(events[1]['at'])-datetime.fromisoformat(events[0]['at'])).total_seconds(),4)
    def test_auto_recurrence_and_pity_are_idempotent(self):
        e=self.event(recurrence_days=7)
        self.run_action('events','signup',{'event':e['id'],'member':self.m,'team':'Front'})
        self.run_action('events','signup',{'event':e['id'],'member':self.n,'team':'Front'})
        self.run_action('events','save',{'id':e['id'],'archived':True})
        self.run_action('events','save',{'id':e['id'],'archived':True})
        self.assertEqual(get(self.g,'member',self.n).data['pity_points'],1)
        first=self.run_action('events','next',{'event':e['id']});second=self.run_action('events','next',{'event':e['id']})
        self.assertEqual(first['id'],second['id'])
    def test_component_signup_and_card_resync(self):
        from guilds.discord_components import event_components,process
        e=self.event();components=event_components(self.g,get(self.g,'event',e['id']))
        process(self.member,components[0]['components'][0]['custom_id'])
        self.assertEqual(len(get(self.g,'event',e['id']).data['signups']),1)
        first=self.run_action('community','post_event',{'event':e['id']})
        self.run_action('events','save',{'id':e['id'],'title':'Changed'})
        second=self.run_action('community','post_event',{'event':e['id']})
        self.assertEqual(first['id'],second['id']);self.assertIn('Changed',second['text'])
    def test_llm_adapter_and_fallback(self):
        from unittest.mock import patch,Mock
        from guilds.modules.ai import generate
        with patch.dict('os.environ',{'OLLAMA_MODEL':''}):self.assertIn('offline',generate('','text','fallback')['mode'])
        reply=Mock();reply.json.return_value={'message':{'content':'Summary'}}
        with patch.dict('os.environ',{'OLLAMA_MODEL':'test'}),patch('httpx.post',return_value=reply):self.assertEqual(generate('','text','fallback')['text'],'Summary')
    def test_roster_source_rejects_private_urls(self):
        from guilds.modules.integrations import fetch_roster
        with self.assertRaises(Invalid):fetch_roster('http://127.0.0.1/private')
    def test_class_lookup_queue_respects_backoff(self):
        self.run_action('intelligence','queue_lookup',{'character':'Enemy'})
        self.run_action('intelligence','lookup_backoff',{'until':'2099-01-01T00:00:00Z'})
        self.assertEqual(self.run_action('intelligence','resolve_queue',{})['resolved'],0)
        self.assertEqual(get(self.g,'lookup','enemy').data['status'],'pending')
    @override_settings(ALLOW_LOCAL_LOGIN=True)
    def test_adoption_key_hidden_and_one_use(self):
        key=self.run_action('admin','adoption_key',{})['key']
        outsider=User.objects.create_user('newowner',password='testing-123')
        self.client.force_login(outsider)
        payload=json.dumps({'guild':self.g.pk,'server_id':'1234','key':key})
        response=self.client.post('/recover/',data=payload,content_type='application/json')
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.client.post('/recover/',data=payload,content_type='application/json').status_code,400)
        data=self.client.get(f'/api/{self.g.pk}/state/').json();self.assertNotIn('adoption',data['records'])
    def test_disband_requires_confirmation_and_deletes_guild(self):
        with self.assertRaises(Invalid):self.run_action('admin','disband',{'confirmation':'wrong'})
        result=self.run_action('admin','disband',{'confirmation':'Guild'})
        self.assertEqual(result['deleted_guild'],self.g.pk);self.assertFalse(Guild.objects.filter(pk=self.g.pk).exists())
    def test_allied_event_view_rejects_outsiders(self):
        e=self.event();shared=self.run_action('events','share',{'event':e['id']})
        outsider=User.objects.create_user('outsider',password='testing-123');self.client.force_login(outsider)
        self.assertEqual(self.client.get('/events/shared/'+shared['share_token']+'/').status_code,403)
        self.client.force_login(self.owner);self.assertEqual(self.client.get('/events/shared/'+shared['share_token']+'/').status_code,200)
    def test_challenge_requires_opponent_acceptance(self):
        from unittest.mock import patch
        with patch('secrets.randbelow',side_effect=[41,50,16]):
            service=self.run_action('operations','challenge',{'opponent':self.m})
            self.assertNotIn('roll',service)
            self.assertEqual(get(self.g,'challenge',service['id']).data['roll'],42)
            with self.assertRaises(PermissionDenied):self.run_action('operations','accept_challenge',{'challenge':service['id']})
            self.client.force_login(self.owner)
            response=self.client.post(f'/api/{self.g.pk}/operations/challenge/',data=json.dumps({'opponent':self.m}),content_type='application/json')
            self.assertEqual(response.status_code,200);created=response.json()['result'];self.assertNotIn('roll',created)
            stored=get(self.g,'challenge',created['id']);self.assertEqual(stored.data['roll'],51)
            for user in [self.owner,self.member]:
                self.client.force_login(user)
                pending=next(item for item in self.client.get(f'/api/{self.g.pk}/state/').json()['records']['challenge'] if item['id']==created['id'])
                self.assertNotIn('roll',pending)
            response=self.client.post(f'/api/{self.g.pk}/operations/accept_challenge/',data=json.dumps({'challenge':created['id']}),content_type='application/json')
            self.assertEqual(response.status_code,200);result=response.json()['result']
            self.assertEqual((result['status'],result['roll'],result['opponent_roll']),('complete',51,17))
            for user in [self.owner,self.member]:
                self.client.force_login(user)
                complete=next(item for item in self.client.get(f'/api/{self.g.pk}/state/').json()['records']['challenge'] if item['id']==created['id'])
                self.assertEqual((complete['roll'],complete['opponent_roll']),(51,17))
            with self.assertRaises(Invalid):self.run_action('operations','accept_challenge',{'challenge':created['id']},self.member)
    def test_capture_update_digest_and_atomic_install(self):
        import tempfile,zipfile,hashlib
        from pathlib import Path
        from guilds.updater import install_release,inspect_release
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);archive=root/'capture.zip'
            with zipfile.ZipFile(archive,'w') as z:z.writestr('capture.py','print("OpenIQ")')
            manifest=root/'manifest.json';data={'version':'0.1.0','archive':'capture.zip','sha256':'bad'};manifest.write_text(json.dumps(data))
            with self.assertRaises(ValueError):install_release(manifest,root/'installed')
            data['sha256']=hashlib.sha256(archive.read_bytes()).hexdigest();manifest.write_text(json.dumps(data))
            self.assertEqual(install_release(manifest,root/'installed')['installed'],'0.1.0')
            self.assertFalse(inspect_release(manifest,root/'installed')['available'])
    def test_capture_update_rejects_traversal(self):
        import tempfile,zipfile,hashlib
        from pathlib import Path
        from guilds.updater import install_release
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);archive=root/'capture.zip'
            with zipfile.ZipFile(archive,'w') as z:z.writestr('../outside.py','bad')
            manifest=root/'manifest.json';manifest.write_text(json.dumps({'version':'0.1.0','archive':'capture.zip','sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}))
            with self.assertRaises(ValueError):install_release(manifest,root/'installed')
            self.assertFalse((root/'outside.py').exists())
