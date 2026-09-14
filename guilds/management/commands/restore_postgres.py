from pathlib import Path
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand,CommandError
from config.database import PostgreSQLBackend,DatabaseOperationError
from guilds.backup_manifest import validate_snapshot


class Command(BaseCommand):
    help='Restore a PostgreSQL snapshot transactionally into the configured dedicated database; stop all writers first.'
    def add_arguments(self,parser):
        parser.add_argument('snapshot',type=Path);parser.add_argument('--overwrite',action='store_true')
        parser.add_argument('--timeout',type=int,default=120)
    def handle(self,*args,**options):
        if not options['overwrite']:raise CommandError('Restoring replaces database objects; stop writers and explicitly pass --overwrite')
        if options['timeout']<1:raise CommandError('timeout must be positive')
        database=settings.DATABASES['default']
        if database['ENGINE']!='django.db.backends.postgresql':raise CommandError('Configure the PostgreSQL destination first')
        source=options['snapshot'].resolve();manifest,filename=validate_snapshot(source)
        if filename!='database.dump':raise CommandError('This is not a PostgreSQL snapshot')
        if (source/'.secret-key').read_text()!=settings.SECRET_KEY:raise CommandError('Configure the snapshot signing key before restoring; keep all services stopped')
        try:PostgreSQLBackend().restore(database,source/filename,options['timeout'])
        except DatabaseOperationError as exc:raise CommandError(str(exc)) from None
        call_command('check',stdout=self.stdout);call_command('migrate',check_unapplied=True,stdout=self.stdout)
        self.stdout.write('PostgreSQL restore completed and Django checks passed.')
