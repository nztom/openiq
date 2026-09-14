"""Validate a SQLite snapshot, check a staged copy, and publish its data directory."""
import hashlib,json,os,shutil,sqlite3,subprocess,sys,tempfile,uuid
from contextlib import closing
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand,CommandError


from guilds.backup_manifest import validate_snapshot


class Command(BaseCommand):
    help='Restore SQLite into a separate data directory. Stop services before replacing their directory.'
    def add_arguments(self,parser):
        parser.add_argument('snapshot',type=Path);parser.add_argument('--output',required=True,type=Path)
        parser.add_argument('--overwrite',action='store_true');parser.add_argument('--timeout',type=int,default=120)

    def handle(self,*args,**options):
        source=options['snapshot'].resolve();target=options['output'].absolute()
        if options['timeout']<1:
            raise CommandError('timeout must be positive')
        if target.is_symlink() or target.resolve()==settings.DATA_DIR.resolve():
            raise CommandError('Use an isolated OPENIQ_DATA_DIR for this command; never replace the running command’s data directory')
        if target.exists() and not options['overwrite']:
            raise CommandError('Output exists; use --overwrite only after stopping all services')
        if target.exists() and not target.is_dir():
            raise CommandError('Output must be a data directory')
        if source==target.resolve() or target.resolve() in source.parents:
            raise CommandError('Backup must be outside the destination directory')
        target.parent.mkdir(parents=True,exist_ok=True)
        manifest,filename=validate_snapshot(source)
        if filename!='db.sqlite3':
            raise CommandError('Use native pg_restore for a PostgreSQL snapshot; this command publishes SQLite directories')
        with tempfile.TemporaryDirectory(prefix='.openiq-restore-',dir=target.parent) as temporary:
            stage=Path(temporary);stage.chmod(0o700)
            for name in ('db.sqlite3','.secret-key','manifest.json'):
                shutil.copyfile(source/name,stage/name);(stage/name).chmod(0o600)
            validate_snapshot(stage)
            try:
                with closing(sqlite3.connect((stage/'db.sqlite3').as_uri()+'?mode=ro',uri=True)) as database:
                    if database.execute('PRAGMA integrity_check').fetchall()!=[('ok',)]:
                        raise ValueError()
            except (sqlite3.Error,ValueError):raise CommandError('Snapshot failed SQLite integrity validation') from None
            environment=os.environ.copy()
            environment.update(OPENIQ_DATA_DIR=str(stage),DATABASE_PATH=str(stage/'db.sqlite3'),DATABASE_BACKEND='sqlite')
            environment.pop('SECRET_KEY',None)
            try:
                for command in (['check'],['migrate','--check']):
                    subprocess.run([sys.executable,str(settings.BASE_DIR/'manage.py'),*command],env=environment,cwd=settings.BASE_DIR,
                                   timeout=options['timeout'],check=True,capture_output=True)
            except (OSError,subprocess.SubprocessError):raise CommandError('Staged restore failed Django or migration checks; destination is unchanged') from None
            previous=None
            if target.exists():
                previous=target.with_name(target.name+'.previous-'+uuid.uuid4().hex[:12])
                os.rename(target,previous)
            try:os.rename(stage,target)
            except OSError:
                if previous:os.rename(previous,target)
                raise
        self.stdout.write('Restored and checked '+str(target))
        if previous:self.stdout.write('Previous directory retained at '+str(previous))
