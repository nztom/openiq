from unittest.mock import AsyncMock,Mock,patch
from asgiref.sync import async_to_sync
from django.contrib.auth.models import User
from django.test import TestCase
from django.core.management import call_command
from .models import Guild,Access,Record
from .modules.commands import COMMANDS
from .modules.core import Invalid
from .discord_commands import build_command,normalize,autocomplete_choices


class NativeCommandTests(TestCase):
    def test_all_commands_build_typed_options_and_normalize(self):
        run=AsyncMock()
        for name in COMMANDS:
            command=build_command(name,run)
            self.assertNotIn('arguments',[p.name for p in command.parameters])
        gear=build_command('gearupdate',run)
        self.assertEqual(next(p for p in gear.parameters if p.name=='ap').type.value,4)
        self.assertTrue(next(p for p in gear.parameters if p.name=='ap').required)
        self.assertEqual(normalize('class',{'member':'id','class_name':'Shai','spec':'Ascension','backfill':True}),{'member':'id','class':'Shai','spec':'Ascension','backfill':True})
        self.assertEqual(normalize('setup',{'names':'Alpha, Beta\nGamma'})['names'],['Alpha','Beta','Gamma'])
        self.assertEqual(normalize('setbotchannel',{'channel':Mock(id=123)})['channel'],'123')
        self.assertEqual(normalize('whois',{'discord_id':Mock(id=456)})['discord_id'],'456')
        self.assertEqual(normalize('sync roster',{}),{})
        self.assertEqual(normalize('event create',{'teams':'Front,20\nBack,10,Support'})['teams'][1],{'name':'Back','capacity':10,'group':'Support'})
        for teams in ['bad','Front,abc']:
            with self.assertRaises(Invalid):normalize('event create',{'teams':teams})
        self.assertEqual(normalize('config',{'setting':'roles','value':'{"member":["1"]}'}),{'config':{'roles':{'member':['1']}}})
        with self.assertRaises(Invalid):normalize('config',{'setting':'roles','value':'[]'})
        with self.assertRaises(Invalid):normalize('config',{})

    def test_autocomplete_is_scoped_and_private(self):
        guild=Guild.objects.create(name='Guild',server_id='123');user=User.objects.create_user('discord_7')
        Record.objects.create(guild=guild,kind='reminder',key='own',data={'user':user.pk,'text':'Own reminder'})
        Record.objects.create(guild=guild,kind='reminder',key='other',data={'user':999,'text':'Private reminder'})
        interaction=Mock();interaction.guild_id=123;interaction.guild.owner_id=7;interaction.user.id=7;interaction.user.roles=[];interaction.user.guild_permissions.value=8;interaction.namespace.guild_name=''
        self.assertEqual([c.value for c in autocomplete_choices('reminder',interaction,'')],['own'])
        self.assertEqual([c.value for c in autocomplete_choices('guild',interaction,'Gui')],['Guild'])
        user.is_active=False;user.save()
        self.assertEqual(autocomplete_choices('guild',interaction,'Gui'),[])
        self.assertEqual(autocomplete_choices('reminder',interaction,''),[])
        user.is_active=True;user.save()
        self.assertEqual(autocomplete_choices('war',interaction,''),[])
        for i in range(26):Record.objects.create(guild=guild,kind='member',key=str(i),data={'name':'Member '+str(i)})
        self.assertEqual(len(autocomplete_choices('member',interaction,'')),25)
        self.assertEqual(autocomplete_choices('member',interaction,'missing'),[])
        Guild.objects.create(name='Other Guild',server_id='123')
        self.assertEqual(autocomplete_choices('member',interaction,''),[])
        interaction.namespace.guild_name='Guild'
        self.assertEqual(len(autocomplete_choices('member',interaction,'')),25)
        interaction.guild.owner_id=999;interaction.user.guild_permissions.value=0
        self.assertEqual(autocomplete_choices('member',interaction,''),[])
        guild.config={'roles':{'member':['42']}};guild.save();interaction.user.roles=[Mock(id=42)]
        self.assertEqual(autocomplete_choices('assignment',interaction,''),[])
        interaction.guild=None
        self.assertEqual(autocomplete_choices('member',interaction,''),[])

    def test_native_link_creates_discord_identity(self):
        guild=Guild.objects.create(name='Guild',server_id='123')
        Record.objects.create(guild=guild,kind='member',key='member',data={'name':'Alpha'})
        with patch.dict('os.environ',{'DISCORD_BOT_TOKEN':'test','ENABLE_DISCORD_DELIVERY':'1'}),patch('discord.Client.run',autospec=True) as connect:call_command('runbot')
        bot=connect.call_args.args[0];interaction=Mock();interaction.guild_id=123;interaction.channel_id=1;interaction.guild.owner_id=7;interaction.user.id=7;interaction.user.roles=[];interaction.user.guild_permissions.value=8
        interaction.response.defer=AsyncMock();interaction.followup.send=AsyncMock()
        async_to_sync(bot.tree.get_command('link').callback)(interaction,member='member',discord_id=Mock(id=99))
        user=User.objects.get(username='discord_99');self.assertFalse(user.has_usable_password())
        self.assertEqual(Record.objects.get(guild=guild,kind='member').data['user_id'],str(user.pk))
