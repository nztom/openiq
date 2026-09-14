import io
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from django.core.management import call_command
from .models import Guild,Record
from .modules.core import save


class RetentionTests(TestCase):
    def test_preview_expiry_live_protection_and_finalized_war_preservation(self):
        g=Guild.objects.create(name='Retention',config={'retention':{'capture_days':1,'recap_days':1,'import_days':1,'summary_days':2}})
        war=save(g,'war',{'participants':[{'member':'member','kills':5,'deaths':1}]})
        event={'id':'1','at':'2026-01-01T00:00:00Z','kind':'kill','player':'A','target':'B','guild':'Enemy','class':'Unknown'}
        session=save(g,'session',{'status':'saved','events':[event],'public':True,'share_token':'token','war':war.key})
        live=save(g,'session',{'status':'live','events':[event],'public':False})
        draft=save(g,'import',{'status':'finalized','rows':[{'name':'A'}],'war':war.key})
        Record.objects.filter(guild=g).update(created=timezone.now()-timedelta(days=3))
        call_command('retention',guild=g.pk,stdout=io.StringIO())
        session.refresh_from_db();self.assertTrue(session.data['events'])
        call_command('retention',guild=g.pk,apply=True,stdout=io.StringIO())
        session.refresh_from_db();live.refresh_from_db();draft.refresh_from_db();war.refresh_from_db()
        self.assertEqual(session.data['events'],[]);self.assertFalse(session.data['public'])
        self.assertNotIn('retained_summary',session.data);self.assertTrue(live.data['events'])
        self.assertEqual(draft.data['rows'],[]);self.assertEqual(war.data['participants'][0]['kills'],5)
