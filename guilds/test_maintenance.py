import io,tempfile,json
from pathlib import Path
from django.test import TestCase
from django.contrib.auth.models import User
from django.core.management import call_command,CommandError
from .models import Guild,Access,Record
from .modules.core import save


class MaintenanceTests(TestCase):
    def setUp(self):
        self.owner=User.objects.create_user('owner');self.member=User.objects.create_user('member')
        self.g=Guild.objects.create(name='Maintain');self.other=Guild.objects.create(name='Other')
        Access.objects.create(user=self.owner,guild=self.g,role='owner')
        Access.objects.create(user=self.member,guild=self.g,role='member');Access.objects.create(user=self.member,guild=self.other,role='member')
    def command(self,operation,**options):return call_command('maintain',operation,guild=self.g.pk,actor='owner',stdout=io.StringIO(),**options)
    def test_preview_removal_keeps_other_guild_and_last_owner(self):
        self.command('remove_user',username='member');self.assertTrue(Access.objects.filter(guild=self.g,user=self.member).exists())
        self.command('remove_user',username='member',apply=True)
        self.assertTrue(Access.objects.filter(guild=self.other,user=self.member).exists())
        with self.assertRaises(CommandError):self.command('remove_user',username='owner',apply=True)
    def test_export_excludes_credentials_and_cleanup_is_scoped(self):
        save(self.g,'capture_token',{'digest':'private','expires':0},'token');save(self.other,'capture_token',{'expires':0},'other')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'guild.json';self.command('export',output=path)
            self.assertNotIn('private',path.read_text());package=json.loads(path.read_text());self.assertEqual(package['format'],'openiq-guild-v1')
            self.assertEqual(set(package),{'format','digest','payload','warnings'});self.assertNotIn('server_id',str(package))
        self.command('cleanup',apply=True)
        self.assertFalse(Record.objects.filter(guild=self.g,kind='capture_token').exists())
        self.assertTrue(Record.objects.filter(guild=self.other,kind='capture_token').exists())
