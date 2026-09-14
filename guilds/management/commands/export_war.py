import json
from pathlib import Path
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from guilds.services import execute


class Command(BaseCommand):
    help='Export one complete war package with linked records and correction history.'
    def add_arguments(self,parser):
        parser.add_argument('--guild',required=True,type=int);parser.add_argument('--war',required=True)
        parser.add_argument('--user',required=True);parser.add_argument('--output',required=True,type=Path)
    def handle(self,*args,**options):
        result=execute(User.objects.get(username=options['user']),options['guild'],'wars','export',{'war':options['war']})
        with options['output'].open('x',encoding='utf-8') as stream:
            options['output'].chmod(0o600);json.dump(result,stream,indent=2)
        self.stdout.write(str(options['output']))
