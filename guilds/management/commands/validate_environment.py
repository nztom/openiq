"""Fail early on missing/unsafe deployment settings without echoing their values."""
import os,re
from urllib.parse import urlparse
from django.conf import settings
from django.core.management.base import BaseCommand,CommandError


def problems(env,debug,service='web'):
    errors=[]
    for key in ('DEBUG','HTTPS','TRUST_PROXY','ALLOW_LOCAL_LOGIN','SEED_DEMO','ENABLE_BACKEND_ADMIN','ENABLE_DISCORD_DELIVERY','DISCORD_SYNC_GLOBAL'):
        if key in env and env[key] not in ('0','1'):errors.append(key+' must be 0 or 1')
    if env.get('ENABLE_DISCORD_DELIVERY')=='1' and not env.get('DISCORD_BOT_TOKEN'):errors.append('Enabled Discord delivery requires DISCORD_BOT_TOKEN')
    if not debug:
        if env.get('REQUEST_LIMITS_ENABLED')=='0':errors.append('Production request limits must remain enabled')
        if env.get('ALLOW_LOCAL_LOGIN')=='1':errors.append('Production member password login must be disabled')
        if env.get('SEED_DEMO')=='1':errors.append('Production demo seeding must be disabled')
        if service=='web':
            if env.get('HTTPS')!='1':errors.append('Production web requires HTTPS=1 and a TLS endpoint')
            hosts=[host.strip() for host in env.get('ALLOWED_HOSTS','localhost,127.0.0.1').split(',') if host.strip()]
            if not hosts or any(not re.fullmatch(r'(?:[A-Za-z0-9][A-Za-z0-9.-]*|\[[0-9a-fA-F:]+\])',host) for host in hosts):errors.append('ALLOWED_HOSTS must contain explicit hostnames without wildcards or URL components')
            for origin in filter(None,env.get('CSRF_TRUSTED_ORIGINS','').split(',')):
                parsed=urlparse(origin.strip())
                if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.path or parsed.query or parsed.fragment:errors.append('Production CSRF_TRUSTED_ORIGINS must contain HTTPS origins only')
            for key in ('DISCORD_CLIENT_ID','DISCORD_CLIENT_SECRET','DISCORD_REDIRECT_URI'):
                if not env.get(key):errors.append('Production requires '+key)
            redirect=urlparse(env.get('DISCORD_REDIRECT_URI',''))
            if redirect.scheme!='https' or not redirect.hostname or redirect.username or redirect.query or redirect.fragment:
                errors.append('Production DISCORD_REDIRECT_URI must be an HTTPS callback URL')
            elif redirect.hostname not in hosts:errors.append('The Discord callback hostname must be listed in ALLOWED_HOSTS')
    for key in ('HSTS_SECONDS',):
        if key in env and (not env[key].isdecimal() or int(env[key])>63072000):errors.append(key+' must be an integer from 0 to 63072000')
    for key in ('RATE_LIMIT_OAUTH','RATE_LIMIT_ADMIN_LOGIN','RATE_LIMIT_RECOVERY','RATE_LIMIT_OCR','RATE_LIMIT_MUTATION'):
        if key in env and (not env[key].isdecimal() or not 1<=int(env[key])<=1000000):errors.append(key+' must be a positive integer up to 1000000')
    if 'SESSION_MAX_AGE' in env and (not env['SESSION_MAX_AGE'].isdecimal() or not 60<=int(env['SESSION_MAX_AGE'])<=604800):errors.append('SESSION_MAX_AGE must be from 60 seconds to 7 days')
    if set(filter(None,env.get('REQUIRED_PROCESSES','').split(',')))-{'bot','scheduler'}:errors.append('REQUIRED_PROCESSES supports scheduler and bot only')
    if env.get('DISCORD_CLIENT_ID') and not env['DISCORD_CLIENT_ID'].isdecimal():errors.append('DISCORD_CLIENT_ID must be numeric')
    if env.get('DISCORD_SYNC_GUILD') and not env['DISCORD_SYNC_GUILD'].isdecimal():errors.append('DISCORD_SYNC_GUILD must be numeric')
    if env.get('DISCORD_SYNC_GUILD') and env.get('DISCORD_SYNC_GLOBAL')=='1':errors.append('Choose one Discord command sync scope')
    return errors


class Command(BaseCommand):
    help='Validate the deployment environment before starting services; never print credentials.'
    def handle(self,*args,**options):
        errors=problems(os.environ,settings.DEBUG,os.getenv('OPENIQ_SERVICE','web'))
        if errors:raise CommandError('\n'.join(errors))
        self.stdout.write('Deployment environment is valid.')
