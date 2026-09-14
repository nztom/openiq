from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from guilds.models import Guild,Record
from guilds.capture_api import pair
from guilds.services import access
from guilds.modules.core import require


class Command(BaseCommand):
    help='Issue a 24-hour capture credential, replacing the previous one, or revoke it.'
    def add_arguments(self,parser):
        parser.add_argument('--guild',required=True,type=int)
        parser.add_argument('--session',required=True)
        parser.add_argument('--user',required=True)
        parser.add_argument('--revoke',action='store_true')
    def handle(self,*args,**options):
        user=User.objects.get(username=options['user']);guild=Guild.objects.get(pk=options['guild'])
        require(access(user,guild))
        if options['revoke']:
            Record.objects.filter(guild=guild,kind='capture_token',key=options['session']).delete()
            self.stdout.write('Capture credential revoked.')
        else:self.stdout.write(pair(user,guild,options['session']))
