from django.core.management.base import BaseCommand,CommandError

from guilds.models import Guild,Record
from guilds.modules.roster import member_errors


class Command(BaseCommand):
    help='Identify malformed member records without changing them.'

    def add_arguments(self,parser):
        parser.add_argument('--guild',type=int,help='Limit the check to one guild ID.')

    def handle(self,*args,**options):
        records=Record.objects.filter(kind='member').select_related('guild').order_by('guild_id','created')
        if options['guild'] is not None:
            if not Guild.objects.filter(pk=options['guild']).exists():raise CommandError('Guild not found')
            records=records.filter(guild_id=options['guild'])
        invalid=[]
        for record in records:
            error=member_errors(record.data)
            if error:
                invalid.append(record)
                self.stdout.write(f'guild={record.guild_id} member={record.key}: {error}')
        if invalid:raise CommandError(f'{len(invalid)} malformed member record(s); correct them with an owner roster edit')
        self.stdout.write(self.style.SUCCESS(f'Roster validation passed for {records.count()} member record(s)'))
