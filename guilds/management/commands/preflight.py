"""Read-only checks for data relationships before an upgrade."""
import json
from django.core.management import call_command
from django.core.management.base import BaseCommand,CommandError
from guilds.models import Guild,Access,Record


class Command(BaseCommand):
    help='Check migrations and guild record relationships before upgrade; does not repair or modify data.'
    def handle(self,*args,**options):
        call_command('check',stdout=self.stdout)
        call_command('migrate',check_unapplied=True,stdout=self.stdout)
        errors=[]
        for guild in Guild.objects.all():
            if not Access.objects.filter(guild=guild,role='owner').exists():errors.append({'guild':guild.pk,'issue':'missing owner'})
            records=list(Record.objects.filter(guild=guild));members={r.key for r in records if r.kind=='member'};wars={r.key for r in records if r.kind=='war'}
            for record in records:
                if record.kind=='war' and any(p.get('member') not in members for p in record.data.get('participants',[])):errors.append({'guild':guild.pk,'record':record.key,'issue':'war participant missing'})
                if record.kind in ('event','session') and record.data.get('war') and record.data['war'] not in wars:errors.append({'guild':guild.pk,'record':record.key,'issue':'linked war missing'})
        self.stdout.write(json.dumps({'passed':not errors,'issues':errors},indent=2))
        if errors:raise CommandError('Preflight failed; resolve reported relationships before upgrading')
