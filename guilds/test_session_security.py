import logging
from unittest.mock import patch
from django.test import TestCase,override_settings
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from .session_security import RedactCredentials


class SessionSecurityTests(TestCase):
    @override_settings(ALLOW_LOCAL_LOGIN=True,SESSION_COOKIE_AGE=600)
    def test_login_rotates_session_sets_absolute_expiry_and_logout_flushes_tokens(self):
        user=User.objects.create_user('login',password='test-password')
        session=self.client.session;session['discord_tokens']={'access':'private'};session.save()
        old=session.session_key
        self.client.post('/login/',{'username':user.username,'password':'test-password'})
        session=self.client.session;self.assertNotEqual(session.session_key,old)
        expiry=session['_session_expiry'];self.assertIsInstance(expiry,str)
        self.assertNotIn('discord_tokens',session)
        session['discord_tokens']={'access':'new-private'};session.save();self.assertEqual(self.client.session['_session_expiry'],expiry)
        key=session.session_key
        self.client.post('/logout/')
        self.assertNotIn('discord_tokens',self.client.session);self.assertFalse(Session.objects.filter(session_key=key).exists())

    def test_logs_redact_credentials_and_callback_codes(self):
        record=logging.LogRecord('test',logging.ERROR,'',0,'GET /callback?code=private&state=other token=%s',('env-secret',),None)
        with patch.dict('os.environ',{'DISCORD_BOT_TOKEN':'env-secret'}):RedactCredentials().filter(record)
        self.assertNotIn('private',record.getMessage());self.assertNotIn('env-secret',record.getMessage());self.assertNotIn('other',record.getMessage())
