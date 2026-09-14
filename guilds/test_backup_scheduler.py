import io
import signal
from pathlib import Path
from unittest.mock import Mock, patch

from django.core.management import call_command, CommandError
from django.test import SimpleTestCase


class BackupSchedulerTests(SimpleTestCase):
    def test_invalid_limits_do_not_start(self):
        for name in ('interval', 'keep', 'timeout'):
            with self.subTest(name=name), self.assertRaises(CommandError):
                call_command('backup_scheduler', output=Path('backups'), **{name: 0})

    def test_failure_retries_and_signal_handlers_are_restored(self):
        stop = Mock()
        stop.is_set.side_effect = [False, False, True]
        stderr = io.StringIO()
        module = 'guilds.management.commands.backup_scheduler.'
        with patch(module + 'threading.Event', return_value=stop), \
                patch(module + 'signal.signal', return_value=signal.SIG_DFL) as register, \
                patch(module + 'call_command', side_effect=[OSError('secret'), None]) as backup:
            call_command('backup_scheduler', output=Path('backups'), interval=30,
                         keep=2, timeout=10, stderr=stderr)
            self.assertEqual(backup.call_count, 2)
            self.assertEqual(backup.call_args.kwargs['keep'], 2)
            self.assertEqual(backup.call_args.kwargs['timeout'], 10)
            self.assertEqual(backup.call_args.kwargs['output'], Path('backups'))
            self.assertEqual(stop.wait.call_args_list, [((30,),), ((30,),)])
            register.call_args_list[0].args[1](signal.SIGTERM, None)
            stop.set.assert_called_once()
            self.assertEqual(register.call_args_list[-1].args, (signal.SIGTERM, signal.SIG_DFL))
            self.assertEqual(register.call_args_list[-2].args, (signal.SIGINT, signal.SIG_DFL))
        self.assertIn('Retrying next interval', stderr.getvalue())
        self.assertNotIn('secret', stderr.getvalue())
