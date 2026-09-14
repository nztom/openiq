import tempfile
from pathlib import Path
from django.test import SimpleTestCase,TestCase,override_settings
from .settings_validation import validate
from .modules.core import Invalid
from .models import Guild
from .integration_status import status
from .health import heartbeat


class SettingsValidationTests(SimpleTestCase):
    def test_typed_nested_values_reject_unsafe_shapes(self):
        for config in ({'roles':{'owner':['everyone']}},{'channels':{'bot':'bad'}},{'tickets':{'staff_role':'bad'}},{'capture':{'token_hours':0}},{'weekly':{'hour':24}},{'command_permissions':{'fake':'owner'}},{'integrations':{'twitch':'yes'}}):
            with self.subTest(config=config),self.assertRaises(Invalid):validate(config)
        validate({'roles':{'member':['123']},'capture':{'enabled':True,'token_hours':24,'diagnostic_entries':50},'weekly':{'hour':20,'weekday':1,'timezone':'UTC'},'integrations':{'twitch':False}})


class IntegrationStatusTests(TestCase):
    def test_status_distinguishes_configuration_and_heartbeat(self):
        guild=Guild.objects.create(name='Status')
        with tempfile.TemporaryDirectory() as directory,override_settings(DATA_DIR=Path(directory)):
            report={r['name']:r for r in status(guild)};self.assertEqual(report['Bot']['status'],'not running')
            heartbeat('bot');report={r['name']:r for r in status(guild)}
            self.assertEqual(report['Bot']['status'],'running');self.assertEqual(report['Capture']['status'],'waiting')
