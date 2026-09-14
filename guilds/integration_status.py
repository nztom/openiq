"""Local integration facts, without credentials or implicit remote requests."""
import json,os,time
from django.conf import settings
from .models import Record,Outbox


def status(guild):
    result=[]
    def add(name,state,detail):result.append({'name':name,'status':state,'detail':detail})
    oauth=bool(os.getenv('DISCORD_CLIENT_ID') and os.getenv('DISCORD_CLIENT_SECRET'))
    add('Discord login','configured' if oauth else 'not configured','The operator configures OAuth credentials and the callback URL; use Discord sign-in to verify them.')
    for process in ('bot','scheduler','backup'):
        try:
            data=json.loads((settings.DATA_DIR/('.heartbeat-'+process+'.json')).read_text())
            fresh=0<=time.time()-data['at']<data.get('max_age',120)
            state='running' if fresh and data['ready'] else 'not ready'
        except (OSError,ValueError,KeyError,TypeError):state='not running'
        add(process.title(),state,'Enable its Compose profile and inspect its logs. Bot permission checks are available with bot_diagnostics.' if process=='bot' else 'Enable its Compose profile and inspect the service logs. Backup success is measured against its configured interval.')
    for provider,keys in (('Twitch',('TWITCH_CLIENT_ID','TWITCH_ACCESS_TOKEN')),('Ollama',('OLLAMA_MODEL',))):
        enabled=guild.config.get('integrations',{}).get(provider.lower(),True)
        add(provider,'disabled' if not enabled else 'configured' if all(os.getenv(key) for key in keys) else 'not configured','The operator supplies credentials/model settings. A configured adapter still needs a real connection check.')
    sessions=Record.objects.filter(guild=guild,kind='session')
    latest=max((r.data.get('capture_last_seen','') for r in sessions),default='')
    add('Capture','disabled' if not guild.config.get('capture',{}).get('enabled',True) else 'batch received' if latest else 'waiting','Last acknowledged batch: '+latest if latest else 'Start a live session, pair capture and forward its log. See CAPTURE_HANDOFF.md.')
    pending=Outbox.objects.filter(guild=guild,status__in=['preview','retry']).count()
    attention=Outbox.objects.filter(guild=guild,status__in=['uncertain','failed']).count()
    add('Discord delivery','enabled' if os.getenv('ENABLE_DISCORD_DELIVERY')=='1' else 'disabled',f'{pending} queued messages; {attention} require operator reconciliation. Enable delivery and the scheduler only after checking channel permissions.')
    add('Member access','configured' if guild.config.get('roles',{}).get('member') else 'needs setup','Configure Discord member roles and notification channels in Settings.')
    return result
