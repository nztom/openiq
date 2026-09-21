"""Opt-in shared dashboard UX checks: OPENIQ_BROWSER_TEST=1."""
import os
from unittest import skipUnless

from django.contrib.auth.models import User
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings

from .models import Access, Guild, Record


@skipUnless(os.getenv('OPENIQ_BROWSER_TEST') == '1', 'Opt-in browser integration')
@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class DashboardUXTests(StaticLiveServerTestCase):
    def test_owner_exports_previews_and_confirms_guild_transfer(self):
        from playwright.sync_api import sync_playwright

        user = User.objects.create_user('portability-ux')
        source = Guild.objects.create(name='Portability A Source')
        target = Guild.objects.create(name='Portability B Target')
        Access.objects.create(user=user, guild=source, role='owner')
        Access.objects.create(user=user, guild=target, role='owner')
        Record.objects.create(guild=source, kind='member', key='portable-member', data={
            'name': 'Portable Family', 'character': '', 'class': 'Unknown',
            'spec': 'Succession', 'active': True, 'exception': False,
            'group': 'Unassigned', 'joined': '2026-09-21',
        })
        self.client.force_login(user)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel=os.getenv('OPENIQ_BROWSER_CHANNEL') or None, headless=True)
            try:
                page = browser.new_page()
                page.context.add_cookies([{'name': 'sessionid', 'value': self.client.cookies['sessionid'].value, 'url': self.live_server_url}])
                page.goto(self.live_server_url)
                page.get_by_role('button', name='Settings', exact=True).click()
                with page.expect_download() as pending:
                    page.get_by_role('button', name='Export guild', exact=True).click()
                export_path = pending.value.path()
                page.get_by_role('combobox', name='Current guild').select_option(str(target.pk))
                page.wait_for_function(f'state && state.guild.id === {target.pk}')
                page.get_by_role('button', name='Settings', exact=True).click()
                page.get_by_role('button', name='Import guild', exact=True).click()
                page.get_by_label('Guild export', exact=True).set_input_files(export_path)
                page.get_by_role('button', name='Preview import', exact=True).click()
                page.get_by_text('1 create', exact=False).wait_for()
                page.get_by_label('Destination guild confirmation', exact=True).fill(target.name)
                page.get_by_role('button', name='Confirm import', exact=True).click()
                page.get_by_text('Imported 1 records', exact=False).wait_for()
                self.assertTrue(page.evaluate("state.records.member.some(item => item.id === 'portable-member')"))
            finally:
                browser.close()

    def test_empty_states_keyboard_and_failed_save(self):
        from playwright.sync_api import sync_playwright

        user = User.objects.create_user('ux-test')
        guild = Guild.objects.create(name='Empty UX guild')
        Access.objects.create(user=user, guild=guild, role='owner')
        self.client.force_login(user)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel=os.getenv('OPENIQ_BROWSER_CHANNEL') or None, headless=True)
            try:
                page = browser.new_page(viewport={'width': 390, 'height': 844}, reduced_motion='reduce')
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.context.add_cookies([{'name': 'sessionid', 'value': self.client.cookies['sessionid'].value, 'url': self.live_server_url}])
                page.goto(self.live_server_url)
                self.assertTrue(page.get_by_role('link', name='OpenIQ on GitHub').last.is_visible())
                history = page.get_by_role('button', name='History', exact=True)
                history.focus()
                page.keyboard.press('Enter')
                self.assertEqual(page.locator('#nav [aria-current="page"]').inner_text(), 'History')
                self.assertEqual(page.evaluate('document.activeElement.textContent'), 'History')
                self.assertGreater(page.get_by_text('No records to show.', exact=False).count(), 0)
                self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
                page.get_by_role('button', name='Members', exact=True).click()
                search = page.get_by_role('textbox', name='Search family name', exact=True)
                search.press_sequentially('KeepTyping')
                self.assertEqual(search.input_value(), 'KeepTyping')
                self.assertTrue(search.evaluate('(el) => document.activeElement === el'))
                self.assertEqual(page.get_by_role('combobox', name='Sort members').count(), 1)
                self.assertEqual(page.get_by_role('combobox', name='Filter by class').count(), 1)
                search.fill('')
                page.get_by_role('button', name='Add member', exact=True).click()
                self.assertEqual(page.get_by_role('dialog').get_attribute('aria-labelledby'), 'dialog-title')
                field = page.get_by_label('Family name', exact=True)
                field.fill('KeepMyInput')
                # A delayed rejection lets us exercise keyboard dismissal and duplicate submit guards.
                page.evaluate("""() => {
                    window.uxCalls = 0;
                    activeAction.custom = () => {
                        window.uxCalls++;
                        return new Promise((resolve, reject) => { window.uxReject = reject; });
                    };
                }""")
                page.get_by_role('button', name='Save', exact=True).click()
                self.assertTrue(page.get_by_role('button', name='Saving...', exact=True).is_disabled())
                self.assertEqual(page.locator('#action-form').get_attribute('aria-busy'), 'true')
                page.keyboard.press('Escape')
                self.assertTrue(page.get_by_role('dialog').is_visible())
                page.evaluate("document.querySelector('#action-form').dispatchEvent(new Event('submit', {cancelable:true}))")
                self.assertEqual(page.evaluate('window.uxCalls'), 1)
                page.evaluate("window.uxReject(new Error('Family name already exists'))")
                page.wait_for_function("document.activeElement.id === 'form-error'")
                self.assertEqual(field.input_value(), 'KeepMyInput')
                self.assertTrue(page.get_by_role('button', name='Save', exact=True).is_enabled())
                field.fill('CorrectedName')
                page.evaluate("() => { activeAction.custom = async payload => {window.uxSaved = payload.name; return {};}; }")
                page.get_by_role('button', name='Save', exact=True).click()
                page.wait_for_function("!document.querySelector('#dialog').open")
                self.assertEqual(page.evaluate('window.uxSaved'), 'CorrectedName')
                self.assertFalse(errors)
            finally:
                browser.close()

    def test_edit_saved_schedules(self):
        from playwright.sync_api import sync_playwright

        user = User.objects.create_user('schedule-ux')
        guild = Guild.objects.create(name='Schedule UX', config={
            'weekly': {'enabled': True, 'weekday': 4, 'hour': 18, 'timezone': 'Australia/Sydney', 'channel': '123', 'extra': 'preserved'},
            'sync': {'enabled': False, 'weekday': 1, 'hour': 3, 'timezone': 'UTC', 'channel': 'preview', 'url': 'https://example.com/roster'},
        })
        Access.objects.create(user=user, guild=guild, role='owner')
        self.client.force_login(user)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel=os.getenv('OPENIQ_BROWSER_CHANNEL') or None, headless=True)
            try:
                page = browser.new_page(viewport={'width': 390, 'height': 844})
                page.context.add_cookies([{'name': 'sessionid', 'value': self.client.cookies['sessionid'].value, 'url': self.live_server_url}])
                page.goto(self.live_server_url)
                page.get_by_role('button', name='Settings', exact=True).click()
                page.get_by_role('button', name='Edit weekly summary schedule').click()
                self.assertEqual(page.get_by_label('Weekday', exact=True).input_value(), 'Friday')
                self.assertEqual(page.get_by_label('Hour (0-23)', exact=True).input_value(), '18')
                page.get_by_label('Hour (0-23)', exact=True).fill('24')
                self.assertFalse(page.get_by_label('Hour (0-23)', exact=True).evaluate('(el) => el.checkValidity()'))
                page.get_by_label('Hour (0-23)', exact=True).fill('19')
                page.get_by_label('Timezone', exact=True).fill('Invalid/Zone')
                page.get_by_role('button', name='Save', exact=True).click()
                page.wait_for_function("document.querySelector('#form-error').textContent === 'Invalid timezone'")
                self.assertEqual(page.get_by_label('Hour (0-23)', exact=True).input_value(), '19')
                saved = page.evaluate("async () => (await (await fetch('/api/' + state.guild.id + '/state/')).json()).guild.config")
                self.assertEqual(saved['weekly']['hour'], 18)
                page.get_by_label('Timezone', exact=True).fill('UTC')
                page.get_by_role('button', name='Save', exact=True).click()
                page.wait_for_function("!document.querySelector('#dialog').open")
                saved = page.evaluate("async () => (await (await fetch('/api/' + state.guild.id + '/state/')).json()).guild.config")
                self.assertEqual(saved['weekly']['hour'], 19)
                self.assertEqual(saved['weekly']['extra'], 'preserved')
                self.assertEqual(saved['sync']['url'], 'https://example.com/roster')
                page.get_by_role('button', name='Edit roster sync schedule').click()
                self.assertEqual(page.get_by_label('Weekday', exact=True).input_value(), 'Tuesday')
                self.assertEqual(page.get_by_label('Hour (0-23)', exact=True).input_value(), '3')
                self.assertFalse(page.get_by_label('Enabled', exact=True).is_checked())
                self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
            finally:
                browser.close()

    def test_application_forms_and_ticket_categories(self):
        from playwright.sync_api import sync_playwright

        user = User.objects.create_user('community-settings-ux')
        guild = Guild.objects.create(name='Community settings UX', config={'channels': {'bot': '123', 'custom': '456'}, 'tickets': {'staff_role': '789'}})
        Access.objects.create(user=user, guild=guild, role='owner')
        self.client.force_login(user)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel=os.getenv('OPENIQ_BROWSER_CHANNEL') or None, headless=True)
            try:
                page = browser.new_page(viewport={'width': 390, 'height': 844})
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.context.add_cookies([{'name': 'sessionid', 'value': self.client.cookies['sessionid'].value, 'url': self.live_server_url}])
                page.goto(self.live_server_url)
                page.get_by_role('button', name='Settings', exact=True).click()
                page.get_by_role('button', name='Configure channels', exact=True).click()
                self.assertEqual(page.get_by_label('Bot commands', exact=True).input_value(), '123')
                page.get_by_label('Welcome messages', exact=True).fill('#welcome')
                page.get_by_role('button', name='Save', exact=True).click()
                page.wait_for_function("document.querySelector('#form-error').textContent.includes('numeric channel ID')")
                self.assertEqual(page.get_by_label('Welcome messages', exact=True).input_value(), '#welcome')
                page.get_by_label('Welcome messages', exact=True).fill('111222333444555666')
                page.get_by_label('Bot commands', exact=True).fill('')
                page.get_by_label('Coaching notifications', exact=True).fill('preview')
                page.get_by_role('button', name='Save', exact=True).click()
                page.wait_for_function("!document.querySelector('#dialog').open")
                saved = page.evaluate('state.guild.config')
                self.assertNotIn('bot', saved['channels'])
                self.assertEqual(saved['channels']['welcome'], '111222333444555666')
                self.assertEqual(saved['channels']['custom'], '456')
                self.assertEqual(saved['channels']['leads'], 'preview')
                self.assertEqual(saved['tickets']['staff_role'], '789')
                self.assertTrue(page.get_by_text('No application forms yet.', exact=False).is_visible())
                self.assertTrue(page.get_by_text('No ticket categories yet.', exact=False).is_visible())
                page.get_by_role('button', name='New application form', exact=True).click()
                page.get_by_label('Form title', exact=True).fill('Raid application')
                questions = page.get_by_label('Questions, one per line (1-20)', exact=True)
                questions.fill('Why join?\nPreferred class?')
                page.get_by_role('button', name='Save', exact=True).click()
                page.wait_for_function("!document.querySelector('#dialog').open")
                page.get_by_role('button', name='Edit Raid application', exact=True).click()
                self.assertEqual(questions.input_value(), 'Why join?\nPreferred class?')
                questions.fill('\n'.join(['Question'] * 21))
                page.get_by_role('button', name='Save', exact=True).click()
                page.wait_for_function("document.querySelector('#form-error').textContent === 'Supply 1-20 application questions'")
                self.assertEqual(page.get_by_label('Form title', exact=True).input_value(), 'Raid application')
                questions.fill('Available days?\nPreferred class?')
                page.get_by_role('button', name='Save', exact=True).click()
                page.wait_for_function("!document.querySelector('#dialog').open")
                self.assertEqual(page.evaluate("records('recruitment_form').length"), 1)
                self.assertTrue(page.get_by_text('Available days?', exact=True).is_visible())
                page.get_by_role('button', name='New ticket category', exact=True).click()
                page.get_by_label('Category name', exact=True).fill('Recruitment')
                page.get_by_label('Staff role ID (optional)', exact=True).fill('not-an-id')
                page.get_by_role('button', name='Save', exact=True).click()
                page.wait_for_function("document.querySelector('#form-error').textContent === 'Staff role ID must contain only digits'")
                page.get_by_label('Staff role ID (optional)', exact=True).fill('123456789012345678')
                page.get_by_role('button', name='Save', exact=True).click()
                page.wait_for_function("!document.querySelector('#dialog').open")
                page.get_by_role('button', name='Edit Recruitment', exact=True).click()
                self.assertEqual(page.get_by_label('Staff role ID (optional)', exact=True).input_value(), '123456789012345678')
                page.get_by_label('Category name', exact=True).fill('Officer support')
                page.get_by_role('button', name='Save', exact=True).click()
                page.wait_for_function("!document.querySelector('#dialog').open")
                self.assertEqual(page.evaluate("records('ticket_category').length"), 1)
                page.reload()
                page.get_by_role('button', name='Settings', exact=True).click()
                self.assertTrue(page.get_by_role('button', name='Edit Officer support', exact=True).is_visible())
                self.assertTrue(page.get_by_text('Available days?', exact=True).is_visible())
                self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
                self.assertFalse(errors)
            finally:
                browser.close()

    def test_capture_retention_integration_settings(self):
        from playwright.sync_api import sync_playwright
        user = User.objects.create_user('remaining-settings')
        guild = Guild.objects.create(name='Settings', config={'channels': {'bot': '123'}})
        Access.objects.create(user=user, guild=guild, role='owner')
        self.client.force_login(user)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={'width': 390, 'height': 844})
                page.context.add_cookies([{'name': 'sessionid', 'value': self.client.cookies['sessionid'].value, 'url': self.live_server_url}])
                page.goto(self.live_server_url)
                page.get_by_role('button', name='Settings', exact=True).click()
                self.assertTrue(page.get_by_role('heading', name='Setup and integration status').is_visible())
                page.get_by_role('button', name='Configure capture', exact=True).click()
                lifetime = page.get_by_label('Pairing lifetime in hours (1-72)', exact=True)
                lifetime.fill('73')
                page.get_by_role('button', name='Save', exact=True).click()
                page.wait_for_function("document.activeElement.id === 'form-error'")
                self.assertEqual(lifetime.input_value(), '73')
                lifetime.fill('12')
                page.get_by_role('button', name='Save', exact=True).click()
                page.wait_for_function("!document.querySelector('#dialog').open")
                self.assertEqual(page.evaluate('state.guild.config.capture.token_hours'), 12)
                page.get_by_role('button', name='Configure retention', exact=True).click()
                page.get_by_label('Saved capture days (0 keeps data)', exact=True).fill('30')
                page.get_by_role('button', name='Save', exact=True).click()
                page.wait_for_function("!document.querySelector('#dialog').open")
                page.get_by_role('button', name='Configure integrations', exact=True).click()
                page.get_by_label('Allow Twitch refresh', exact=True).uncheck()
                page.get_by_role('button', name='Save', exact=True).click()
                page.wait_for_function("!document.querySelector('#dialog').open")
                page.reload()
                page.get_by_role('button', name='Settings', exact=True).click()
                self.assertEqual(page.evaluate('state.guild.config.retention.capture_days'), 30)
                self.assertFalse(page.evaluate('state.guild.config.integrations.twitch'))
                self.assertEqual(page.evaluate('state.guild.config.channels.bot'), '123')
                self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
            finally:
                browser.close()

    def test_every_empty_section_and_load_failure(self):
        from playwright.sync_api import sync_playwright
        user=User.objects.create_user('all-sections')
        guild=Guild.objects.create(name='No demo data')
        Access.objects.create(user=user,guild=guild,role='owner')
        self.client.force_login(user)
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(headless=True)
            try:
                page=browser.new_page(viewport={'width':390,'height':844}, reduced_motion='reduce')
                errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
                page.context.add_cookies([{'name':'sessionid','value':self.client.cookies['sessionid'].value,'url':self.live_server_url}])
                page.goto(self.live_server_url)
                page.wait_for_selector('#nav button')
                from pathlib import Path
                page.add_script_tag(path=str(Path(__file__).resolve().parents[1]/'node_modules/axe-core/axe.min.js'))
                self.assertFalse(errors)
                for width in (390,1280):
                    page.set_viewport_size({'width':width,'height':844})
                    for section in page.locator('#nav button').all_text_contents():
                        nav=page.get_by_role('button',name=section,exact=True);nav.focus();page.keyboard.press('Enter')
                        self.assertEqual(page.locator('#title').inner_text(),section)
                        self.assertTrue(page.locator('#panel').inner_text().strip(),section)
                        self.assertTrue(page.evaluate('document.documentElement.scrollWidth<=innerWidth'),section)
                        self.assertEqual(page.evaluate('document.activeElement.textContent'),section)
                        violations=page.evaluate("async () => (await axe.run(document, {runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}})).violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)}))")
                        self.assertFalse(violations, section+': '+str(violations))
                # Inspect the accessibility tree and every available action dialog.
                page.set_viewport_size({'width':390,'height':844})
                actions=page.evaluate('state.actions.map(a=>({module:a.module,action:a.action,label:a.label}))')
                for action in actions:
                    page.evaluate('(a)=>openAction(state.actions.find(x=>x.module===a.module && x.action===a.action))',action)
                    self.assertIn('dialog',page.get_by_role('dialog').aria_snapshot())
                    violations=page.evaluate("async () => (await axe.run(document, {runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}})).violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)}))")
                    self.assertFalse(violations,action['label']+': '+str(violations))
                    self.assertTrue(page.evaluate('document.querySelector("#dialog").scrollWidth<=document.querySelector("#dialog").clientWidth'),action['label'])
                    page.keyboard.press('Escape')
                    self.assertFalse(page.get_by_role('dialog').is_visible())
                before=page.locator('#panel').inner_text()
                page.route('**/state/**',lambda route:route.fulfill(status=503,body='Unavailable'))
                page.get_by_role('button',name='Refresh',exact=False).click()
                page.wait_for_function("!document.querySelector('#error').hidden")
                self.assertEqual(page.locator('#panel').inner_text(),before)
                self.assertEqual(page.locator('#load-status').inner_text(),'Update failed')
                page.unroute('**/state/**')
                page.get_by_role('button',name='Refresh',exact=False).click()
                page.wait_for_function("document.querySelector('#error').hidden")
                self.assertFalse(errors)
            finally:browser.close()
