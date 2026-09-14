import signal,threading
from django.core.management.base import BaseCommand
from django.core.management import call_command
from guilds.health import heartbeat
class Command(BaseCommand):
    help='Run scheduled jobs continuously; outbound delivery requires ENABLE_DISCORD_DELIVERY=1.'
    def add_arguments(self,p):p.add_argument('--interval',type=int,default=30)
    def handle(self,*args,**o):
        stop=threading.Event()
        previous={}
        try:
            for sig in [signal.SIGINT,signal.SIGTERM]:previous[sig]=signal.signal(sig,lambda *_:stop.set())
            while not stop.is_set():
                try:call_command('tick',stdout=self.stdout,stop_event=stop);heartbeat('scheduler')
                except Exception:
                    heartbeat('scheduler',False);self.stderr.write('Scheduled run failed; check database and integration configuration.')
                stop.wait(max(1,o['interval']))
        finally:
            heartbeat('scheduler',False)
            for sig,handler in previous.items():signal.signal(sig,handler)
