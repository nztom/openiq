import io
from django.test import TestCase
from django.core.management import call_command,CommandError
from django.contrib.auth.models import User
from .models import Guild,Access
from .modules.core import save


class PreflightTests(TestCase):
    def test_valid_and_damaged_relationships_without_mutation(self):
        guild=Guild.objects.create(name='Upgrade');user=User.objects.create_user('owner')
        Access.objects.create(guild=guild,user=user,role='owner')
        call_command('preflight',stdout=io.StringIO())
        record=save(guild,'session',{'war':'missing'})
        with self.assertRaises(CommandError):call_command('preflight',stdout=io.StringIO())
        record.refresh_from_db();self.assertEqual(record.data,{'war':'missing'})
        guild.refresh_from_db();self.assertEqual(guild.revision,0)
