"""Prune configured raw/derived data while preserving finalized war records."""
import json
from datetime import timedelta
from django.core.management.base import BaseCommand,CommandError
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from guilds.models import Guild,Record,Audit
from guilds.modules.live import summarize


class Command(BaseCommand):
    help='Preview retention changes; --apply clears expired raw data and public sharing, never finalized wars.'
    def add_arguments(self,parser):
        parser.add_argument('--guild',required=True,type=int);parser.add_argument('--apply',action='store_true')

    @transaction.atomic
    def handle(self,*args,**options):
        Guild.objects.filter(pk=options['guild']).update(revision=F('revision')+1)
        guild=Guild.objects.get(pk=options['guild']);config=guild.config.get('retention',{})
        keys=('capture_days','import_days','recap_days','summary_days')
        for key in keys:
            value=config.get(key,0)
            if isinstance(value,bool) or not isinstance(value,int) or not 0<=value<=36500:raise CommandError(key+' must be an integer from 0 to 36500; 0 disables expiry.')
        report={key:0 for key in keys};now=timezone.now()
        for record in Record.objects.filter(guild=guild,kind__in=['session','import']):
            changed=False
            # Creation timestamps are not extended by viewing or retention runs.
            def expired(key):return config.get(key,0)>0 and record.created<now-timedelta(days=config[key])
            if record.kind=='session' and record.data.get('status')!='live':
                if expired('capture_days') and record.data.get('events'):
                    record.data['retained_summary']=summarize(record)
                    record.data['events']=[];record.data['capture_diagnostics']=[];record.data['raw_expired']=True
                    report['capture_days']+=1;changed=True
                if expired('recap_days') and record.data.get('public'):
                    record.data['public']=False;record.data.pop('share_token',None)
                    report['recap_days']+=1;changed=True
                if expired('summary_days') and 'retained_summary' in record.data:
                    record.data.pop('retained_summary');record.data['summary_expired']=True
                    report['summary_days']+=1;changed=True
            if record.kind=='import' and expired('import_days') and record.data.get('rows'):
                record.data['rows']=[];record.data['raw_expired']=True
                if record.data['status']=='review':record.data['status']='expired'
                report['import_days']+=1;changed=True
            if changed and options['apply']:record.save()
        if options['apply']:Audit.objects.create(guild=guild,actor='maintenance',action='retention.apply',data=report)
        else:transaction.set_rollback(True)
        self.stdout.write(json.dumps({'applied':options['apply'],'counts':report}))
