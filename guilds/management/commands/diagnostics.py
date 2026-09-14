import json
from django.core.management.base import BaseCommand,CommandError
from guilds.health import readiness


class Command(BaseCommand):
    help='Report readiness without revealing credentials or private paths.'
    def handle(self,*args,**options):
        report=readiness();self.stdout.write(json.dumps(report,indent=2))
        if report['status']!='ok':raise CommandError('Readiness checks failed')
