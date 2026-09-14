from django.test import TestCase,override_settings
from django.contrib.auth.models import User,AnonymousUser
from django.core.exceptions import PermissionDenied
from .models import Guild,Access,Record
from .catalog import ACTIONS
from .modules.commands import COMMANDS,minimum_role
from .services import execute


@override_settings(REQUEST_LIMITS_ENABLED=False)
class PermissionMatrixTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.guild=Guild.objects.create(name='Matrix')
        cls.users={role:User.objects.create_user(role) for role in ('owner','admin','member')}
        for role,user in cls.users.items():Access.objects.create(guild=cls.guild,user=user,role=role)

    def test_every_http_action_rejects_unauthenticated_and_lower_roles(self):
        tiers={'member':0,'admin':1,'owner':2}
        internal=[{'module':module,'action':action,'role':role} for module,action,role in [('admin','settings','owner'),('community','summary_text','member'),('community','roast','member'),('integrations','streams_fixture','admin'),('live','ingest','admin'),('wars','finalize','admin')]]
        for action in [*ACTIONS,*internal]:
            url=f'/api/{self.guild.pk}/{action["module"]}/{action["action"]}/'
            self.client.logout()
            with self.subTest(action=action['action'],role='anonymous'):self.assertEqual(self.client.post(url,{},content_type='application/json').status_code,302)
            for role,user in self.users.items():
                if tiers[role]>=tiers[action['role']]:continue
                self.client.force_login(user)
                with self.subTest(action=action['action'],role=role):self.assertEqual(self.client.post(url,{},content_type='application/json').status_code,403)

    def test_every_command_rejects_unauthenticated_and_lower_roles(self):
        tiers={'member':0,'admin':1,'owner':2}
        for command in COMMANDS:
            payload={'command':command,'arguments':{}}
            with self.subTest(command=command,role='anonymous'),self.assertRaises(PermissionDenied):execute(AnonymousUser(),self.guild.pk,'commands','run',payload)
            for role,user in self.users.items():
                if tiers[role]>=tiers[minimum_role(command)]:continue
                with self.subTest(command=command,role=role),self.assertRaises(PermissionDenied):execute(user,self.guild.pk,'commands','run',payload)

    def test_private_record_types_and_other_guild_directory_are_hidden(self):
        other=Guild.objects.create(name='Unrelated')
        for kind in ('capture_token','adoption','war_revision','delivery_retry','ticket_channel','welcome_delivery','import','lead','assignment'):
            Record.objects.create(guild=self.guild,kind=kind,key=kind,data={'secret':'private'})
        self.client.force_login(self.users['member'])
        response=self.client.get(f'/api/{self.guild.pk}/state/').json()
        self.assertNotIn('private',str(response));self.assertNotIn(other.name,str(response['guilds']))
