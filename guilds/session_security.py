"""Absolute login lifetime and credential-safe logging."""
import logging,os,re
from datetime import timedelta
from django.conf import settings
from django.utils import timezone


def login_lifetime(sender,request,user,**kwargs):
    if request is not None:
        for key in ('discord_tokens','discord_checked','discord_guilds','oauth_state'):request.session.pop(key,None)
        request.session.set_expiry(timezone.now()+timedelta(seconds=settings.SESSION_COOKIE_AGE))


def redact(value):
    text=str(value)
    for key in ('SECRET_KEY','DISCORD_CLIENT_SECRET','DISCORD_BOT_TOKEN','TWITCH_ACCESS_TOKEN','DATABASE_PASSWORD'):
        secret=os.getenv(key)
        if secret:text=text.replace(secret,'[redacted]')
    text=re.sub(r'(?i)(Bearer|Bot)\s+[A-Za-z0-9._~+/-]{12,}',r'\1 [redacted]',text)
    return re.sub(r'(?i)((?:code|state|access_token|refresh_token|token|secret|password|key)=)[^&\s\"\']+',r'\1[redacted]',text)


class RedactCredentials(logging.Filter):
    def filter(self,record):
        record.msg=redact(record.getMessage());record.args=()
        if record.exc_info:record.exc_text=redact(logging.Formatter().formatException(record.exc_info))
        return True
