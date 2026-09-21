import json,time
from django.test import TestCase,override_settings
from django.contrib.auth.models import User
from .models import Guild,Access,Record


@override_settings(ALLOW_LOCAL_LOGIN=False)
class OnboardingTests(TestCase):
    def assert_invalid_payloads(self):
        payloads=[('[]','Onboarding payload must be a JSON object'),('null','Onboarding payload must be a JSON object'),('"text"','Onboarding payload must be a JSON object'),('123','Onboarding payload must be a JSON object'),('{',None),(json.dumps({'server_id':'1'}),None)]
        for body,error in payloads:
            with self.subTest(body=body):
                response=self.client.post('/onboard/',data=body,content_type='application/json')
                self.assertEqual(response.status_code,400)
                if error:self.assertEqual(response.json(),{'error':error})
                self.assertEqual((Guild.objects.count(),Access.objects.count(),Record.objects.count()),(0,0,0))

    @override_settings(ALLOW_LOCAL_LOGIN=True)
    def test_local_onboarding_rejects_malformed_and_non_object_json_atomically(self):
        self.client.force_login(User.objects.create_user('local-onboarding'))
        self.assert_invalid_payloads()

    def test_production_onboarding_rejects_malformed_and_non_object_json_atomically(self):
        user=User.objects.create_user('discord_invalid');self.client.force_login(user)
        session=self.client.session;session['discord_tokens']={'access':'test'}
        session['discord_guilds']=[{'id':'1','name':'Managed','permissions':'32'}];session['discord_checked']=time.time();session.save()
        self.assert_invalid_payloads()

    def test_first_run_only_shows_manageable_servers_and_validates_region(self):
        user=User.objects.create_user('discord_123');self.client.force_login(user)
        session=self.client.session;session['discord_tokens']={'access':'test'};session['discord_checked']=time.time()
        session['discord_guilds']=[{'id':'1','name':'Managed','permissions':'32'},{'id':'2','name':'Forbidden','permissions':'0'}];session.save()
        self.assertRedirects(self.client.get('/'),'/onboard/',fetch_redirect_response=False)
        response=self.client.get('/onboard/');self.assertContains(response,'Managed');self.assertNotContains(response,'Forbidden')
        self.assertEqual(self.client.post('/onboard/',{'name':'Guild','server_id':'1','region':'BAD'},content_type='application/json').status_code,400)
        self.assertEqual(self.client.post('/onboard/',{'name':'Guild','server_id':'1','region':'EU'},content_type='application/json').status_code,200)
        self.assertEqual(Guild.objects.get().region,'EU')
