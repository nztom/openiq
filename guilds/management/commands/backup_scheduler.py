"""Run bounded online backups at a fixed delay, with interruptible shutdown."""
import signal
import threading
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from guilds.health import heartbeat


class Command(BaseCommand):
    help = 'Back up immediately, then wait between snapshots; retry failures next interval.'

    def add_arguments(self, parser):
        parser.add_argument('--output', required=True, type=Path)
        parser.add_argument('--interval', type=int, default=86400)
        parser.add_argument('--keep', type=int, default=7)
        parser.add_argument('--timeout', type=int, default=120)

    def handle(self, *args, **options):
        if any(options[name] < 1 for name in ('interval', 'keep', 'timeout')):
            raise CommandError('interval, keep and timeout must be positive')
        stop = threading.Event()
        previous = {}
        try:
            for sig in (signal.SIGINT, signal.SIGTERM):
                previous[sig] = signal.signal(sig, lambda *_: stop.set())
            while not stop.is_set():
                try:
                    call_command('backup', output=options['output'], keep=options['keep'],
                                 timeout=options['timeout'], stdout=self.stdout)
                    heartbeat('backup',max_age=options['interval']+options['timeout']+60)
                except Exception:
                    heartbeat('backup',False)
                    # Do not print exception text: backend errors can contain credentials.
                    self.stderr.write('Backup failed; check storage, permissions and database configuration. Retrying next interval.')
                stop.wait(options['interval'])
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)
