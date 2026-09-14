from unittest.mock import patch
from django.test import TestCase,override_settings
from .rate_limits import consume
from .models import RequestLimit


class RequestLimitTests(TestCase):
    def test_shared_limit_expiry_and_private_identity(self):
        with patch('guilds.rate_limits.time.time',return_value=120):
            self.assertTrue(consume('ip:private','oauth',1)[0]);self.assertFalse(consume('ip:private','oauth',1)[0])
        self.assertNotIn('private',RequestLimit.objects.get().key)
        with patch('guilds.rate_limits.time.time',return_value=180):self.assertTrue(consume('ip:private','oauth',1)[0])
        self.assertEqual(RequestLimit.objects.count(),1)

    @override_settings(REQUEST_LIMITS={'oauth':1,'recovery':1,'ocr':1,'mutation':1},REQUEST_LIMITS_ENABLED=True)
    def test_response_retry_and_spoofed_forwarding_header(self):
        self.client.get('/login/')
        response=self.client.get('/login/',HTTP_X_FORWARDED_FOR='203.0.113.9')
        self.assertEqual(response.status_code,429);self.assertIn('Retry-After',response)
