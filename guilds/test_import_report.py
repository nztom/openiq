import io,json
from unittest.mock import patch
from django.core.management import call_command,CommandError
from django.test import SimpleTestCase


class ImportReportTests(SimpleTestCase):
    def test_all_formats_and_dependency_failure_report(self):
        output=io.StringIO()
        with patch('guilds.management.commands.verify_imports.ocr',side_effect=['TestAlpha\nTestBeta','11 2\n7 3']):
            call_command('verify_imports',stdout=output)
        report=json.loads(output.getvalue());self.assertTrue(report['passed']);self.assertEqual(len(report['checks']),4)
        output=io.StringIO()
        with patch('guilds.management.commands.verify_imports.ocr',side_effect=RuntimeError('missing engine')),self.assertRaises(CommandError):
            call_command('verify_imports',stdout=output)
        report=json.loads(output.getvalue());self.assertFalse(report['passed']);self.assertEqual(report['checks'][1]['status'],'fail')
