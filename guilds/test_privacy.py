from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from .models import Guild,Access,Record
from .services import execute
from .modules.core import get


class PrivacyTests(TestCase):
    def test_self_export_anonymization_and_membership_deletion_are_scoped(self):
        owner=User.objects.create_user('owner');user=User.objects.create_user('private-user')
        guild=Guild.objects.create(name='Privacy');other=Guild.objects.create(name='Other')
        Access.objects.create(user=owner,guild=guild,role='owner');Access.objects.create(user=user,guild=guild,role='member');Access.objects.create(user=user,guild=other,role='member')
        member=execute(owner,guild.pk,'roster','save',{'name':'PrivateFamily'})
        execute(owner,guild.pk,'roster','link',{'member':member['id'],'user_id':user.pk,'discord_id':'123456'})
        war=execute(owner,guild.pk,'wars','save',{'participants':[{'member':member['id'],'kills':7,'deaths':2}]})
        ticket=execute(user,guild.pk,'community','ticket',{'subject':'Help','text':'private@example.test'})
        data=execute(user,guild.pk,'privacy','export',{'member':member['id']});self.assertEqual(data['format'],'openiq-member-v1')
        stranger=User.objects.create_user('stranger');Access.objects.create(user=stranger,guild=guild,role='member')
        with self.assertRaises(PermissionDenied):execute(stranger,guild.pk,'privacy','export',{'member':member['id']})
        execute(user,guild.pk,'privacy','delete',{'member':member['id'],'confirmation':'PrivateFamily'})
        self.assertTrue(get(guild,'member',member['id']).data['anonymized'])
        self.assertEqual(get(guild,'war',war['id']).data['participants'][0]['kills'],7)
        self.assertFalse(Record.objects.filter(guild=guild,kind='ticket',key=ticket['id']).exists())
        self.assertFalse(Access.objects.filter(user=user,guild=guild).exists());self.assertTrue(Access.objects.filter(user=user,guild=other).exists())
