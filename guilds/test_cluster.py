from unittest.mock import Mock,patch
from asgiref.sync import async_to_sync
from django.contrib.auth.models import User
from django.test import TestCase
from .models import Guild,Access,Record
from .services import execute
from .discord_commands import autocomplete
from .modules.core import save


class ClusterBoundaryTests(TestCase):
    def test_shared_server_roles_records_and_allied_server_boundaries(self):
        user=User.objects.create_user('discord_7');partner=User.objects.create_user('partner')
        first=Guild.objects.create(name='First',server_id='100',config={'roles':{'member':['10']}})
        second=Guild.objects.create(name='Second',server_id='100',config={'roles':{'member':['20']}})
        allied=Guild.objects.create(name='Allied',server_id='200')
        Access.objects.create(user=user,guild=first,role='owner')
        Access.objects.create(user=partner,guild=allied,role='owner')
        member=execute(user,first.pk,'roster','save',{'name':'FirstFamily'})
        save(second,'member',{'name':'SecondPrivate'},'second')
        save(allied,'member',{'name':'AllyFamily','class':'Shai','active':True,'notes':['Officer secret']},'ally')
        save(allied,'ticket',{'subject':'Private support','text':'Support secret'},'ticket')
        save(allied,'session',{'title':'Private capture','events':[]},'session')
        self.client.force_login(user)
        self.assertEqual(self.client.get(f'/api/{second.pk}/state/').status_code,403)
        self.assertEqual(self.client.post(f'/api/{second.pk}/roster/save/',{'name':'Intruder'},content_type='application/json').status_code,403)
        invitation=execute(user,first.pk,'alliances','create',{'name':'Alliance','partners':[allied.pk]})
        execute(partner,allied.pk,'alliances','respond',{'alliance':invitation['id'],'response':'accepted'})
        data=self.client.get(f'/api/{first.pk}/state/').json()
        self.assertEqual([g['name'] for g in data['guilds']],['First'])
        self.assertIn('AllyFamily',str(data['records']['alliance']))
        for secret in ('SecondPrivate','Officer secret','Support secret','Private capture'):
            self.assertNotIn(secret,str(data))
        self.assertEqual(self.client.get(f'/api/{allied.pk}/state/').status_code,403)
        interaction=Mock();interaction.guild_id=100;interaction.guild.owner_id=999
        interaction.user.id=7;interaction.user.guild_permissions.value=0;interaction.user.roles=[Mock(id=10)]
        interaction.namespace.guild_name='First'
        self.assertEqual([x.value for x in async_to_sync(autocomplete('member'))(interaction,'')],[member['id']])
        interaction.namespace.guild_name='Second'
        self.assertEqual(async_to_sync(autocomplete('member'))(interaction,''),[])
        interaction.namespace.guild_name='Allied'
        self.assertEqual(async_to_sync(autocomplete('member'))(interaction,''),[])
        execute(partner,allied.pk,'alliances','leave',{'alliance':invitation['id']})
        self.assertNotIn('AllyFamily',str(self.client.get(f'/api/{first.pk}/state/').json()))
