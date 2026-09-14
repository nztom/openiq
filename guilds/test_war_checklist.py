from django.test import TestCase
from django.contrib.auth.models import User
from .models import Guild,Access,Outbox
from .modules.core import save
from .war_checklist import checklist


class WarChecklistTests(TestCase):
    def test_lifecycle_and_guild_privacy(self):
        g=Guild.objects.create(name='War');other=Guild.objects.create(name='Other')
        self.assertEqual(checklist(g),[])
        event=save(g,'event',{'title':'Battle','signups':[{'waitlisted':False},{'waitlisted':True}],'locked':True},'event')
        session=save(g,'session',{'title':'Capture','status':'saved','events':[]},'session')
        war=save(g,'war',{'date':'2026-09-12','result':'Win','session':session.key},'war')
        event.data['war']=war.key;event.save()
        Outbox.objects.create(guild=g,key=f'{g.pk}:event:event',status='sent')
        save(g,'import',{'status':'review','rows':[{'member':''}]},'draft')
        save(other,'event',{'title':'Private'},'other')
        rows=checklist(g);self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]['signup'],{'status':'locked','confirmed':1,'waitlisted':1})
        self.assertEqual(rows[0]['result'],'Win');self.assertEqual(rows[0]['discord'],'sent')
        self.assertEqual(rows[1]['corrections'],1)
        user=User.objects.create_user('member');Access.objects.create(user=user,guild=g,role='member')
        self.client.force_login(user)
        # Derived officer data is excluded just like imports and outbox state.
        from unittest.mock import patch
        with patch('guilds.views.analytics.calculate',return_value={}),patch('guilds.views.intelligence.extended',return_value={}),patch('guilds.views.gear.rankings',return_value=[]):
            self.assertNotIn('war_checklist',self.client.get(f'/api/{g.pk}/state/').json())
