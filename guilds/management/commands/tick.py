from django.core.management.base import BaseCommand,CommandError
from guilds.models import Guild,Access
from guilds.services import execute
class Command(BaseCommand):
    stealth_options=('stop_event',)
    help='Process scheduled work once; outbound delivery requires explicit enablement.'
    def handle(self,*args,**options):
        failed=[]
        for g in Guild.objects.all():
            if options.get('stop_event') and options['stop_event'].is_set():return
            owner=Access.objects.filter(guild=g,role='owner').select_related('user').first()
            if owner:
                try:self.stdout.write(str(execute(owner.user,g.pk,'operations','tick',{})))
                except Exception:
                    failed.append(g.pk)
                    self.stderr.write(f'Scheduled work failed for guild {g.pk}; inspect its settings and integrations.')
        from guilds.delivery import send_due
        self.stdout.write(str(send_due(stop_event=options.get('stop_event'))))
        if failed:raise CommandError('Scheduled work failed for guild IDs: '+', '.join(map(str,failed)))
