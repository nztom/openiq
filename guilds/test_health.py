import tempfile
from pathlib import Path
from unittest.mock import patch
from django.test import TestCase,override_settings
from .health import heartbeat,readiness


class HealthTests(TestCase):
    def test_database_failure_does_not_fail_liveness(self):
        with patch('guilds.health.connection.cursor',side_effect=RuntimeError('secret')):
            self.assertEqual(self.client.get('/healthz/').status_code,200)
            response=self.client.get('/readyz/');self.assertEqual(response.status_code,503)
            self.assertNotIn('secret',response.content.decode())

    def test_required_process_heartbeat_and_expiry(self):
        with tempfile.TemporaryDirectory() as directory,override_settings(DATA_DIR=Path(directory),REQUIRED_PROCESSES=['scheduler']):
            self.assertFalse(readiness()['checks']['scheduler'])
            heartbeat('scheduler');self.assertTrue(readiness()['checks']['scheduler'])
            with patch('guilds.health.time.time',return_value=10**12):self.assertFalse(readiness()['checks']['scheduler'])
            heartbeat('scheduler',False);self.assertFalse(readiness()['checks']['scheduler'])
