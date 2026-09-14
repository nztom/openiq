"""Rotate the explicitly enabled break-glass Django admin credential."""
import json,os,secrets,tempfile
from pathlib import Path
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand,CommandError
from django.db import transaction

class Command(BaseCommand):
    help='Enable and rotate, or disable, the managed backend-only administrator account.'
    def handle(self,*args,**options):
        username=os.getenv('BACKEND_ADMIN_USERNAME','openiq-admin').strip()
        if not username or len(username)>150:raise CommandError('BACKEND_ADMIN_USERNAME must contain 1–150 characters')
        enabled=os.getenv('ENABLE_BACKEND_ADMIN','0')=='1'
        destination=settings.DATA_DIR/'.backend-admin.json'
        with transaction.atomic():
            user=User.objects.filter(username=username).first()
            if not enabled:
                if user:user.is_staff=False;user.is_superuser=False;user.set_unusable_password();user.save()
                destination.unlink(missing_ok=True)
                self.stdout.write(f'OpenIQ backend admin disabled ({username}).')
                return
            password=secrets.token_urlsafe(24)
            user,_=User.objects.get_or_create(username=username)
            user.is_active=True;user.is_staff=True;user.is_superuser=True;user.set_password(password);user.save()
            with tempfile.NamedTemporaryFile(mode='w',dir=settings.DATA_DIR,delete=False,encoding='utf-8') as stream:
                temporary=Path(stream.name)
                try:
                    json.dump({'url':'/admin/','username':username,'password':password},stream)
                    stream.flush();os.fsync(stream.fileno())
                except BaseException:
                    stream.close();temporary.unlink(missing_ok=True)
                    raise
            try:
                temporary.chmod(0o600)
                os.replace(temporary,destination)
            finally:temporary.unlink(missing_ok=True)
        self.stdout.write(self.style.WARNING('OPENIQ BACKEND ADMIN CREDENTIAL ROTATED'))
        self.stdout.write(f'Private credential file: {destination}')
        self.stdout.write(self.style.WARNING('Retrieve the credential through private operator access; it changes on the next web-container start.'))
