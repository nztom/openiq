from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client,TestCase

from .models import Access,Guild,Record
from .modules.analytics import calculate
from .modules.core import Invalid,get
from .services import execute


class RosterValidationTests(TestCase):
    def setUp(self):
        self.owner=User.objects.create_user('roster-owner')
        self.guild=Guild.objects.create(name='Roster validation')
        Access.objects.create(guild=self.guild,user=self.owner,role='owner')

    def save(self,payload):
        return execute(self.owner,self.guild.pk,'roster','save',payload)

    def test_invalid_types_and_bounds_do_not_write(self):
        cases=[
            {'name':'Broken','class':[]},
            {'name':'Broken','character':None},
            {'name':'Broken','group':{}},
            {'name':'Broken','spec':'Invalid'},
            {'name':'Broken','active':'false'},
            {'name':'Broken','exception':0},
            {'name':'Broken','class':'x'*41},
        ]
        for payload in cases:
            with self.subTest(payload=payload),self.assertRaises(Invalid):self.save(payload)
        self.assertFalse(Record.objects.filter(guild=self.guild,kind='member').exists())

    def test_http_rejection_is_a_useful_400(self):
        client=Client();client.force_login(self.owner)
        response=client.post(f'/api/{self.guild.pk}/roster/save/',data='{"name":"Broken","class":[]}',content_type='application/json')
        self.assertEqual(response.status_code,400)
        self.assertEqual(response.json(),{'ok':False,'error':'class must be text containing at most 40 characters'})
        self.assertFalse(Record.objects.filter(guild=self.guild,kind='member').exists())

    def test_partial_edits_and_empty_optional_text_are_supported(self):
        member=self.save({'name':'Alpha','character':'','group':'','active':False,'exception':True})
        edited=self.save({'id':member['id'],'character':'  Ranger  '})
        self.assertEqual(edited['character'],'Ranger')
        self.assertEqual(edited['group'],'')
        self.assertFalse(edited['active'])
        self.assertTrue(edited['exception'])

    def test_rejected_update_rolls_back_and_state_remains_usable(self):
        member=self.save({'name':'Alpha'})
        with self.assertRaises(Invalid):self.save({'id':member['id'],'class':[]})
        self.assertEqual(get(self.guild,'member',member['id']).data['class'],'Unknown')
        self.assertIn('composition',calculate(self.guild))

    def test_existing_malformed_record_can_be_found_and_corrected(self):
        record=Record.objects.create(guild=self.guild,kind='member',key='broken',data={
            'name':'Broken','character':'','class':[],'spec':'Succession','joined':'2026-01-01',
            'active':True,'exception':False,'group':'Unassigned',
        })
        with self.assertRaises(CommandError):call_command('validate_roster',guild=self.guild.pk)
        self.save({'id':record.key,'class':'Unknown'})
        call_command('validate_roster',guild=self.guild.pk)

    def test_class_backfill_requires_a_real_boolean(self):
        member=self.save({'name':'Alpha'})
        with self.assertRaises(Invalid):execute(self.owner,self.guild.pk,'roster','class',{'member':member['id'],'class':'Shai','backfill':'false'})
