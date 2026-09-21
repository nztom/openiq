"""Versioned, guild-scoped exports that are safe to move between instances."""
import copy
import hashlib
import hmac
import json
import math
import re

from django.db import transaction
from django.db.models import F

from .models import Audit, Guild, Record
from .modules.core import Invalid, now

FORMAT = 'openiq-guild-v1'
MAX_PACKAGE_BYTES = 4 * 1024 * 1024
MAX_RECORDS = 50000
PORTABLE_KINDS = frozenset({
    'member', 'group', 'war', 'event', 'template', 'gear', 'retention',
    'lead', 'assignment',
})
PORTABLE_CONFIG = frozenset({
    'performance', 'retention', 'capture', 'integrations', 'milestones',
    'weekly', 'sync', 'welcome', 'command_permissions',
})
EXTERNAL_KEYS = frozenset({
    'user_id', 'discord_id', 'twitch', 'share_token', 'channel', 'channels',
    'message_id', 'server_id', 'guild_id', 'role_id', 'staff_role', 'url',
    'token', 'secret', 'password',
})
SENSITIVE_KEY_PARTS = ('token', 'secret', 'password', 'credential', 'api_key', 'access_key', 'oauth', 'webhook')
KEY_PATTERN = re.compile(r'^[^\x00-\x1f]{1,180}$')


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False,
                      sort_keys=True, separators=(',', ':')).encode()


def _redact(value):
    if isinstance(value, dict):
        return {key: _redact(item) for key, item in value.items()
                if str(key).lower() not in EXTERNAL_KEYS
                and not any(part in str(key).lower() for part in SENSITIVE_KEY_PARTS)}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return copy.deepcopy(value)


def export_guild(guild):
    config = {key: _redact(value) for key, value in guild.config.items()
              if key in PORTABLE_CONFIG}
    records = [
        {'kind': item.kind, 'key': item.key, 'data': _redact(item.data)}
        for item in Record.objects.filter(guild=guild, kind__in=PORTABLE_KINDS)
        .order_by('kind', 'created', 'key')
    ]
    payload = {
        'guild': {'name': guild.name, 'region': guild.region, 'config': config},
        'records': records,
        'exported_at': now(),
    }
    return {
        'format': FORMAT,
        'digest': hashlib.sha256(_canonical(payload)).hexdigest(),
        'payload': payload,
        'warnings': [
            'Account links, Discord/Twitch identifiers, channels, roles, URLs, credentials, and delivery state are excluded.',
            'Review conflicts and reconnect external integrations after import.',
        ],
    }


def _validate_json(value, depth=0):
    if depth > 20:
        raise Invalid('Import data is nested too deeply')
    if value is None or isinstance(value, (bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise Invalid('Invalid number')
        return
    if isinstance(value, str):
        if len(value) > 100000:
            raise Invalid('Import contains an oversized text value')
        return
    if isinstance(value, list):
        for item in value:
            _validate_json(item, depth + 1)
        return
    if isinstance(value, dict):
        if len(value) > 10000:
            raise Invalid('Import object has too many fields')
        for key, item in value.items():
            if not isinstance(key, str) or len(key) > 100:
                raise Invalid('Import field names must be short text values')
            _validate_json(item, depth + 1)
        return
    raise Invalid('Import contains an unsupported value')


def _validate_record(item):
    kind, data = item['kind'], item['data']
    text_fields = {
        'member': ('name',), 'group': ('name',), 'war': ('date',),
        'event': ('title',), 'template': ('name',), 'retention': ('at',),
        'lead': ('name',), 'assignment': ('member', 'lead', 'status'),
        'gear': ('member',),
    }
    for field in text_fields[kind]:
        if not isinstance(data.get(field), str) or not data[field]:
            raise Invalid(f'Import {kind} record requires {field}')
    list_fields = {'war': ('participants',), 'event': ('teams', 'signups')}
    for field in list_fields.get(kind, ()):
        if not isinstance(data.get(field), list):
            raise Invalid(f'Import {kind} record requires {field}')
    if kind == 'template' and not isinstance(data.get('event'), dict):
        raise Invalid('Import template record requires event')
    if kind == 'retention' and (isinstance(data.get('members'), bool) or not isinstance(data.get('members'), int)):
        raise Invalid('Import retention record requires member count')
    if kind == 'lead' and (isinstance(data.get('capacity'), bool) or not isinstance(data.get('capacity'), int)):
        raise Invalid('Import lead record requires capacity')
    for field in ('participants', 'signups'):
        for relationship in data.get(field, []):
            if not isinstance(relationship, dict) or not isinstance(relationship.get('member'), str):
                raise Invalid(f'Import {kind} record has an invalid {field} member')


def validate_package(package):
    if not isinstance(package, dict) or set(package) != {'format', 'digest', 'payload', 'warnings'}:
        raise Invalid('Import must be an OpenIQ guild export')
    if package['format'] != FORMAT:
        raise Invalid('Unsupported guild export version')
    payload = package['payload']
    _validate_json(payload)
    if not isinstance(package['warnings'], list) or not all(isinstance(x, str) for x in package['warnings']):
        raise Invalid('Import warnings are invalid')
    expected = hashlib.sha256(_canonical(payload)).hexdigest()
    if not isinstance(package['digest'], str) or not hmac.compare_digest(package['digest'], expected):
        raise Invalid('Import integrity check failed')
    if not isinstance(payload, dict) or set(payload) != {'guild', 'records', 'exported_at'}:
        raise Invalid('Import payload has an invalid structure')
    source = payload['guild']
    if not isinstance(source, dict) or set(source) != {'name', 'region', 'config'}:
        raise Invalid('Import guild metadata is invalid')
    if not isinstance(source['name'], str) or not source['name'].strip() or len(source['name']) > 80:
        raise Invalid('Import guild name is invalid')
    if not isinstance(source['region'], str) or len(source['region']) > 12:
        raise Invalid('Import guild region is invalid')
    if not isinstance(source['config'], dict) or any(key not in PORTABLE_CONFIG for key in source['config']):
        raise Invalid('Import configuration contains unsupported fields')
    records = payload['records']
    if not isinstance(records, list) or len(records) > MAX_RECORDS:
        raise Invalid(f'Import may contain at most {MAX_RECORDS} records')
    seen = set()
    for item in records:
        if not isinstance(item, dict) or set(item) != {'kind', 'key', 'data'}:
            raise Invalid('Import record structure is invalid')
        if item['kind'] not in PORTABLE_KINDS:
            raise Invalid('Import contains an unsupported record type')
        if not isinstance(item['key'], str) or not KEY_PATTERN.fullmatch(item['key']):
            raise Invalid('Import record key is invalid')
        if not isinstance(item['data'], dict):
            raise Invalid('Import record data must be an object')
        _validate_record(item)
        identity = (item['kind'], item['key'])
        if identity in seen:
            raise Invalid('Import contains duplicate record keys')
        seen.add(identity)
    return payload


def preview_import(guild, package):
    payload = validate_package(package)
    existing = {(row.kind, row.key): row.data for row in Record.objects.filter(guild=guild)}
    create, skip, conflicts = [], [], []
    for item in payload['records']:
        identity = (item['kind'], item['key'])
        if identity not in existing:
            create.append(identity)
        elif existing[identity] == item['data']:
            skip.append(identity)
        else:
            conflicts.append(identity)
    members = {key for kind, key in existing if kind == 'member'}
    members.update(item['key'] for item in payload['records'] if item['kind'] == 'member')
    leads = {key for kind, key in existing if kind == 'lead'}
    leads.update(item['key'] for item in payload['records'] if item['kind'] == 'lead')
    for item in payload['records']:
        references = []
        if item['kind'] == 'war':
            references.extend(('member', row['member']) for row in item['data']['participants'])
        if item['kind'] == 'event':
            references.extend(('member', row['member']) for row in item['data']['signups'])
        if item['kind'] in ('gear', 'assignment'):
            references.append(('member', item['data']['member']))
        if item['kind'] == 'assignment':
            references.append(('lead', item['data']['lead']))
        for reference_kind, reference in references:
            available = members if reference_kind == 'member' else leads
            if reference not in available:
                conflicts.append(('reference', f"{item['kind']}:{item['key']}->{reference_kind}:{reference}"))
    config_create, config_skip, config_conflicts = [], [], []
    for key, value in payload['guild']['config'].items():
        if key not in guild.config:
            config_create.append(key)
        elif guild.config[key] == value:
            config_skip.append(key)
        else:
            config_conflicts.append(key)
    conflicts.extend(('config', key) for key in config_conflicts)
    describe = lambda values: [{'kind': kind, 'key': key} for kind, key in values[:100]]
    return {
        'format': FORMAT,
        'digest': package['digest'],
        'source': {'name': payload['guild']['name'], 'region': payload['guild']['region']},
        'create': len(create) + len(config_create),
        'skip': len(skip) + len(config_skip),
        'reject': len(conflicts),
        'conflicts': describe(conflicts),
        'warnings': package['warnings'],
        'manual_reconfiguration': ['accounts', 'Discord server/channels/roles', 'Twitch links', 'integration URLs and credentials'],
    }


@transaction.atomic
def import_guild(guild, user, package, expected_digest, confirmation):
    locked = Guild.objects.select_for_update().get(pk=guild.pk)
    if confirmation != locked.name:
        raise Invalid('Type the destination guild name to confirm import')
    preview = preview_import(locked, package)
    if not isinstance(expected_digest, str) or not hmac.compare_digest(expected_digest, preview['digest']):
        raise Invalid('Import changed after preview; preview it again')
    if preview['reject']:
        raise Invalid('Resolve import conflicts before confirming')
    payload = validate_package(package)
    existing = {(row.kind, row.key): row.data for row in Record.objects.filter(guild=locked)}
    created = []
    for item in payload['records']:
        identity = (item['kind'], item['key'])
        if identity not in existing:
            created.append(Record(guild=locked, kind=item['kind'], key=item['key'], data=item['data']))
    Record.objects.bulk_create(created)
    merged = copy.deepcopy(locked.config)
    for key, value in payload['guild']['config'].items():
        merged.setdefault(key, value)
    locked.config = merged
    locked.revision = F('revision') + 1
    locked.save(update_fields=['config', 'revision'])
    Audit.objects.create(guild=locked, actor=user.username, action='portability.import', data={
        'format': FORMAT, 'digest': preview['digest'], 'source': payload['guild']['name'],
        'created': len(created), 'skipped': preview['skip'],
    })
    return {'created': len(created), 'skipped': preview['skip'], 'digest': preview['digest']}
