import copy
import hashlib
import json

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from .models import Access, Audit, Guild, Record
from .portability import MAX_PACKAGE_BYTES
from .modules.core import Invalid
from .views import _portability_request


class GuildPortabilityTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('source-owner')
        self.other = User.objects.create_user('other')
        self.source = Guild.objects.create(
            name='Source Guild', region='EU',
            config={
                'performance': {'enabled': True},
                'channels': {'bot': '123'},
                'sync': {'enabled': True, 'url': 'https://example.invalid/private', 'channel': '456'},
                'integrations': {'enabled': True, 'api_key': 'private-key', 'oauth_token': 'private-token'},
            },
        )
        Access.objects.create(guild=self.source, user=self.owner, role='owner')
        Access.objects.create(guild=self.source, user=self.other, role='admin')
        self.member = Record.objects.create(guild=self.source, kind='member', key='member-1', data={
            'name': 'Family', 'class': 'Witch', 'user_id': self.owner.pk,
            'discord_id': '999', 'twitch': 'streamer', 'notes': [{'text': 'Private coaching'}],
        })
        self.war = Record.objects.create(guild=self.source, kind='war', key='war-1', data={
            'date': '2026-09-20', 'participants': [{'member': self.member.key, 'kills': 3, 'deaths': 1}],
        })
        Record.objects.create(guild=self.source, kind='ticket', key='ticket-1', data={'channel': '777', 'text': 'not portable'})

    def login(self, user):
        self.client.force_login(user)

    def package(self):
        self.login(self.owner)
        return self.client.get(f'/api/{self.source.pk}/portability/export/').json()

    def resign(self, package):
        package['digest'] = hashlib.sha256(json.dumps(
            package['payload'], ensure_ascii=False, allow_nan=False,
            sort_keys=True, separators=(',', ':'),
        ).encode()).hexdigest()
        return package

    def test_owner_download_is_versioned_redacted_and_not_retained(self):
        self.login(self.owner)
        response = self.client.get(f'/api/{self.source.pk}/portability/export/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment;', response['Content-Disposition'])
        self.assertEqual(response['Cache-Control'], 'no-store')
        package = response.json()
        self.assertEqual(package['format'], 'openiq-guild-v1')
        self.assertNotIn('channels', package['payload']['guild']['config'])
        self.assertEqual(package['payload']['guild']['config']['sync'], {'enabled': True})
        self.assertEqual(package['payload']['guild']['config']['integrations'], {'enabled': True})
        self.assertNotIn('private-key', json.dumps(package))
        records = {(item['kind'], item['key']): item['data'] for item in package['payload']['records']}
        self.assertEqual(set(kind for kind, _ in records), {'member', 'war'})
        self.assertNotIn('user_id', records[('member', 'member-1')])
        self.assertNotIn('discord_id', records[('member', 'member-1')])
        self.assertNotIn('twitch', records[('member', 'member-1')])
        self.assertEqual(Audit.objects.count(), 0)

    def test_non_owner_cannot_export_preview_or_import(self):
        package = self.package()
        self.login(self.other)
        self.assertEqual(self.client.get(f'/api/{self.source.pk}/portability/export/').status_code, 403)
        for endpoint in ('preview', 'import'):
            response = self.client.post(
                f'/api/{self.source.pk}/portability/{endpoint}/',
                data=json.dumps({'package': package}), content_type='application/json',
            )
            self.assertEqual(response.status_code, 403)

    def test_preview_then_confirm_import_creates_and_skips_atomically(self):
        package = self.package()
        target_owner = User.objects.create_user('target-owner')
        target = Guild.objects.create(name='Target Guild', config={})
        Access.objects.create(guild=target, user=target_owner, role='owner')
        source_member = next(item for item in package['payload']['records'] if item['kind'] == 'member')
        Record.objects.create(guild=target, **source_member)
        self.login(target_owner)
        preview = self.client.post(
            f'/api/{target.pk}/portability/preview/',
            data=json.dumps({'package': package}), content_type='application/json',
        ).json()['preview']
        self.assertEqual((preview['create'], preview['skip'], preview['reject']), (4, 1, 0))
        wrong = self.client.post(
            f'/api/{target.pk}/portability/import/',
            data=json.dumps({'package': package, 'digest': preview['digest'], 'confirmation': 'wrong'}),
            content_type='application/json',
        )
        self.assertEqual(wrong.status_code, 400)
        self.assertFalse(Record.objects.filter(guild=target, kind='war').exists())
        result = self.client.post(
            f'/api/{target.pk}/portability/import/',
            data=json.dumps({'package': package, 'digest': preview['digest'], 'confirmation': target.name}),
            content_type='application/json',
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['result']['created'], 1)
        target.refresh_from_db()
        self.assertEqual(target.config['performance'], {'enabled': True})
        self.assertEqual(target.config['sync'], {'enabled': True})
        self.assertEqual(target.config['integrations'], {'enabled': True})
        self.assertTrue(Record.objects.filter(guild=target, kind='war', key='war-1').exists())
        audit = Audit.objects.get(guild=target, action='portability.import')
        self.assertEqual(audit.data['digest'], package['digest'])
        again = self.client.post(
            f'/api/{target.pk}/portability/preview/',
            data=json.dumps({'package': package}), content_type='application/json',
        ).json()['preview']
        self.assertEqual((again['create'], again['skip'], again['reject']), (0, 5, 0))

    def test_tampering_conflicts_and_oversize_fail_without_partial_writes(self):
        package = self.package()
        target_owner = User.objects.create_user('target-owner')
        target = Guild.objects.create(name='Target Guild')
        Access.objects.create(guild=target, user=target_owner, role='owner')
        self.login(target_owner)
        tampered = copy.deepcopy(package)
        tampered['payload']['records'][0]['data']['name'] = 'Changed'
        response = self.client.post(
            f'/api/{target.pk}/portability/preview/', data=json.dumps({'package': tampered}),
            content_type='application/json',
        )
        self.assertContains(response, 'integrity check failed', status_code=400)
        conflicting = copy.deepcopy(package)
        payload = conflicting['payload']
        self.resign(conflicting)
        Record.objects.create(guild=target, kind='member', key='member-1', data={'name': 'Existing'})
        preview = self.client.post(
            f'/api/{target.pk}/portability/preview/', data=json.dumps({'package': conflicting}),
            content_type='application/json',
        ).json()['preview']
        self.assertEqual(preview['reject'], 1)
        confirm = self.client.post(
            f'/api/{target.pk}/portability/import/',
            data=json.dumps({'package': conflicting, 'digest': preview['digest'], 'confirmation': target.name}),
            content_type='application/json',
        )
        self.assertContains(confirm, 'Resolve import conflicts', status_code=400)
        self.assertFalse(Record.objects.filter(guild=target, kind='war').exists())
        oversized = RequestFactory().post('/', data='{}', content_type='application/json')
        oversized.META['CONTENT_LENGTH'] = str(MAX_PACKAGE_BYTES + 1)
        with self.assertRaisesMessage(Invalid, 'exceeds 4 MiB'):
            _portability_request(oversized)

    def test_invalid_record_schema_and_dangling_references_are_rejected(self):
        package = self.package()
        target_owner = User.objects.create_user('target-owner')
        target = Guild.objects.create(name='Target Guild')
        Access.objects.create(guild=target, user=target_owner, role='owner')
        self.login(target_owner)
        malformed = copy.deepcopy(package)
        next(item for item in malformed['payload']['records'] if item['kind'] == 'war')['data'].pop('participants')
        self.resign(malformed)
        response = self.client.post(
            f'/api/{target.pk}/portability/preview/', data=json.dumps({'package': malformed}),
            content_type='application/json',
        )
        self.assertContains(response, 'requires participants', status_code=400)
        dangling = copy.deepcopy(package)
        dangling['payload']['records'] = [item for item in dangling['payload']['records'] if item['kind'] != 'member']
        self.resign(dangling)
        preview = self.client.post(
            f'/api/{target.pk}/portability/preview/', data=json.dumps({'package': dangling}),
            content_type='application/json',
        ).json()['preview']
        self.assertEqual(preview['reject'], 1)
        self.assertEqual(preview['conflicts'][0]['kind'], 'reference')
