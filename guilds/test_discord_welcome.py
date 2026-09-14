from unittest.mock import Mock,patch
import httpx
from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from .models import Guild,Access,Record
from .services import execute
from .modules.core import Invalid,get
from .discord_welcome import choose,components
from .discord_components import process

class WelcomeTests(TestCase):
    def setUp(self):
        self.owner=User.objects.create_user('owner');self.user=User.objects.create_user('member')
        self.g=Guild.objects.create(name='Guild',server_id='100',config={'welcome':{'roles':['Raider','Social'],'role_ids':{'Raider':'200','Social':'300'}}})
        Access.objects.create(guild=self.g,user=self.owner,role='owner');Access.objects.create(guild=self.g,user=self.user,role='member')
        self.m=execute(self.owner,self.g.pk,'roster','save',{'name':'Alpha'})['id']
        execute(self.owner,self.g.pk,'roster','link',{'member':self.m,'user_id':self.user.pk,'discord_id':'400'})
    def test_card_buttons_and_local_self_selection(self):
        card=execute(self.owner,self.g.pk,'community','welcome',{'member':self.m,'message':'Welcome aboard'})
        buttons=Record.objects.get(kind='message_components',key=str(card['id'])).data['components']
        with patch('httpx.put') as network:
            result=process(self.user,buttons[0]['components'][0]['custom_id']);network.assert_not_called()
        self.assertEqual(result['community_roles'],['Raider']);self.assertEqual(result['delivery'],'local')
        self.assertEqual(choose(self.user,self.g,self.m,'200')['community_roles'],['Raider'])
    def test_only_linked_member_or_officer_can_choose(self):
        other=execute(self.owner,self.g.pk,'roster','save',{'name':'Beta'})['id']
        with self.assertRaises(PermissionDenied):choose(self.user,self.g,other,'200')
        with self.assertRaises(Invalid):choose(self.user,self.g,self.m,'999')
        self.g.config['welcome']['roles']=['Social']
        with self.assertRaises(Invalid):choose(self.user,self.g,self.m,'200')
        self.assertEqual(components(Guild(name='Empty'),get(self.g,'member',self.m)),[])
    def test_remote_role_grant_and_failure_do_not_fake_local_success(self):
        context=patch('guilds.discord_welcome.role_context',return_value=({'200':{'position':1}},10))
        context.start();self.addCleanup(context.stop)
        with patch.dict('os.environ',{'ENABLE_DISCORD_DELIVERY':'0'}),self.assertRaises(Invalid):choose(self.user,self.g,self.m,'200',True)
        with patch.dict('os.environ',{'ENABLE_DISCORD_DELIVERY':'1','DISCORD_BOT_TOKEN':'test'}),patch('httpx.put',side_effect=httpx.ConnectError('offline')),self.assertRaises(httpx.ConnectError):choose(self.user,self.g,self.m,'200',True)
        self.assertNotIn('community_roles',get(self.g,'member',self.m).data)
        with patch.dict('os.environ',{'ENABLE_DISCORD_DELIVERY':'1','DISCORD_BOT_TOKEN':'test'}),patch('httpx.put',return_value=Mock()) as request:
            result=choose(self.user,self.g,self.m,'200',True)
            self.assertTrue(request.call_args.args[0].endswith('/guilds/100/members/400/roles/200'));self.assertEqual(result['delivery'],'Discord')

    def test_role_hierarchy_and_manage_roles_validation(self):
        from .discord_welcome import role_context,manageable
        responses=[]
        for data in ({'id':'900'},{'roles':['800']},[{'id':'800','position':10,'permissions':str(1<<28)},{'id':'200','position':1,'permissions':'0'}]):
            response=Mock();response.json.return_value=data;responses.append(response)
        with patch.dict('os.environ',{'DISCORD_BOT_TOKEN':'test'}),patch('httpx.get',side_effect=responses):
            roles,highest=role_context('100')
        manageable(roles,highest,'100','200')
        for role in ('100','800','999'):
            with self.assertRaises(Invalid):manageable(roles,highest,'100',role)
        roles['200']['managed']=True
        with self.assertRaises(Invalid):manageable(roles,highest,'100','200')
        responses[-1].json.return_value=[{'id':'800','position':10,'permissions':'0'}]
        with patch.dict('os.environ',{'DISCORD_BOT_TOKEN':'test'}),patch('httpx.get',side_effect=responses),self.assertRaisesMessage(Invalid,'Manage Roles'):role_context('100')

    def test_replace_only_removes_roles_previously_granted_by_openiq(self):
        self.g.config['welcome']['replace_selection']=True;self.g.save()
        from .modules.core import save
        save(self.g,'welcome_delivery',{'roles':['300']},self.m)
        with patch.dict('os.environ',{'ENABLE_DISCORD_DELIVERY':'1','DISCORD_BOT_TOKEN':'test'}),patch('guilds.discord_welcome.role_context',return_value=({'200':{'position':1},'300':{'position':2}},10)),patch('httpx.put',return_value=Mock()),patch('httpx.delete',return_value=Mock()) as remove:
            result=choose(self.user,self.g,self.m,'200',True)
        self.assertEqual(result['community_roles'],['Raider'])
        self.assertTrue(remove.call_args.args[0].endswith('/roles/300'))
        self.assertEqual(Record.objects.get(kind='welcome_delivery').data['roles'],['200'])
