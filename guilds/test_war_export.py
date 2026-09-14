from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from .models import Guild,Access,Record
from .services import execute


class WarExportTests(TestCase):
    def test_edit_history_export_and_member_denial(self):
        owner=User.objects.create_user('owner');member=User.objects.create_user('member')
        g=Guild.objects.create(name='Export');Access.objects.create(guild=g,user=owner,role='owner');Access.objects.create(guild=g,user=member,role='member')
        def act(action,payload):return execute(owner,g.pk,'wars',action,payload)
        m=execute(owner,g.pk,'roster','save',{'name':'Alpha'})
        war=act('save',{'participants':[{'member':m['id'],'kills':1,'deaths':2}]})
        act('save',{'id':war['id'],'result':'Win','participants':[{'member':m['id'],'kills':3,'deaths':2}]})
        package=act('export',{'war':war['id']})
        self.assertEqual(len(package['war_revision']),2)
        self.assertEqual(package['war_revision'][1]['before']['participants'][0]['kills'],1)
        self.assertEqual(package['war_revision'][1]['after']['participants'][0]['kills'],3)
        self.assertEqual(package['members'][0]['name'],'Alpha')
        with self.assertRaises(PermissionDenied):execute(member,g.pk,'wars','export',{'war':war['id']})
        act('delete',{'war':war['id']})
        self.assertEqual(Record.objects.filter(kind='war_revision').count(),3)
