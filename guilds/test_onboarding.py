import time
from django.test import TestCase,override_settings
from django.contrib.auth.models import User
from .models import Guild


@override_settings(ALLOW_LOCAL_LOGIN=False)
class OnboardingTests(TestCase):
    def test_first_run_only_shows_manageable_servers_and_validates_region(self):
        user=User.objects.create_user('discord_123');self.client.force_login(user)
        session=self.client.session;session['discord_tokens']={'access':'test'};session['discord_checked']=time.time()
        session['discord_guilds']=[{'id':'1','name':'Managed','permissions':'32'},{'id':'2','name':'Forbidden','permissions':'0'}];session.save()
        self.assertRedirects(self.client.get('/'),'/onboard/',fetch_redirect_response=False)
        response=self.client.get('/onboard/');self.assertContains(response,'Managed');self.assertNotContains(response,'Forbidden')
        self.assertEqual(self.client.post('/onboard/',{'name':'Guild','server_id':'1','region':'BAD'},content_type='application/json').status_code,400)
        self.assertEqual(self.client.post('/onboard/',{'name':'Guild','server_id':'1','region':'EU'},content_type='application/json').status_code,200)
        self.assertEqual(Guild.objects.get().region,'EU')
