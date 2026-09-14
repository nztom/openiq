import os,time
from unittest import skipUnless
from django.contrib.auth.models import User
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from .models import Guild


@skipUnless(os.getenv('OPENIQ_BROWSER_TEST')=='1','Opt-in browser integration')
@override_settings(DEBUG=True,ALLOW_LOCAL_LOGIN=False,SECURE_SSL_REDIRECT=False,SESSION_COOKIE_SECURE=False,CSRF_COOKIE_SECURE=False)
class OnboardingBrowserTests(StaticLiveServerTestCase):
    def test_select_server_correct_failure_and_create_workspace(self):
        from playwright.sync_api import sync_playwright
        user=User.objects.create_user('discord_123');self.client.force_login(user)
        session=self.client.session;session['discord_tokens']={'access':'test'};session['discord_checked']=time.time();session['discord_guilds']=[{'id':'123','name':'My server','permissions':'32'}];session.save()
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(headless=True)
            try:
                page=browser.new_page(viewport={'width':390,'height':844})
                page.context.add_cookies([{'name':'sessionid','value':self.client.cookies['sessionid'].value,'url':self.live_server_url}])
                page.goto(self.live_server_url);page.get_by_label('Guild name',exact=True).fill('New guild')
                page.get_by_label('Region',exact=True).select_option('EU')
                page.route('**/onboard/',lambda route:route.fulfill(status=400,content_type='application/json',body='{"error":"Try another name"}') if route.request.method=='POST' else route.continue_())
                page.get_by_role('button',name='Create guild workspace').click()
                page.wait_for_function("document.activeElement.id==='setup-error'")
                self.assertEqual(page.get_by_label('Guild name',exact=True).input_value(),'New guild')
                page.unroute('**/onboard/')
                page.get_by_role('button',name='Create guild workspace').click()
                page.wait_for_selector('#nav')
                self.assertTrue(page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
            finally:browser.close()
        self.assertEqual(Guild.objects.get().region,'EU')
