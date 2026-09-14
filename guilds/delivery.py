"""Opt-in Discord delivery with durable claims and explicit uncertain outcomes."""
import json
import os
from datetime import timedelta

import httpx
from django.db import transaction
from django.db.models import F,Q
from django.utils import timezone
from django.utils.crypto import salted_hmac
from .models import Outbox,Record
from .modules.core import save,Invalid


def payload_for(item):
    payload={'content':item.text,'allowed_mentions':{'parse':[]},'components':[],'embeds':[]}
    components=Record.objects.filter(guild=item.guild,kind='message_components',key=str(item.pk)).first()
    if components:
        payload['components']=components.data['components']
        payload['embeds']=components.data.get('embeds',[])
    return payload


def deliver(item,enabled=False,queued=False):
    if not enabled:return {'status':'preview','text':item.text,'channel':item.channel}
    if os.getenv('ENABLE_DISCORD_DELIVERY')!='1' or not os.getenv('DISCORD_BOT_TOKEN'):raise Invalid('Discord delivery is not enabled')
    now=timezone.now()
    Outbox.objects.filter(pk=item.pk,status='sending',lease_until__lte=now).update(status='uncertain',last_error='Worker stopped during delivery; reconcile the remote message')
    with transaction.atomic():
        item=Outbox.objects.get(pk=item.pk)
        if not item.channel.isdecimal():
            raise Invalid('Set a numeric Discord channel ID before delivery')
        eligible=Outbox.objects.filter(pk=item.pk).exclude(status__in=['sending','uncertain','cancelled'])
        if queued:eligible=eligible.filter(status__in=['preview','retry']).filter(Q(retry_at__isnull=True)|Q(retry_at__lte=now))
        claimed=eligible.update(status='sending',attempts=F('attempts')+1,lease_until=now+timedelta(seconds=90))
        if not claimed:
            return {'status':Outbox.objects.get(pk=item.pk).status}
        item=Outbox.objects.select_related('guild').get(pk=item.pk)
        payload=payload_for(item)
    previous=Record.objects.filter(guild=item.guild,kind='delivery',key=str(item.pk)).first()
    if previous and previous.data['channel']!=item.channel:previous=None
    url=f'https://discord.com/api/v10/channels/{item.channel}/messages'
    if previous:url+='/'+previous.data['message_id']
    method='PATCH' if previous else 'POST'
    outgoing=dict(payload)
    outgoing['embeds']=[*payload['embeds'],{'footer':{'text':f'OpenIQ delivery {item.guild_id}:{item.pk}'}}]
    if not previous:
        outgoing.update(nonce=salted_hmac('openiq.outbox',f'{item.pk}:{item.channel}').hexdigest()[:24],enforce_nonce=True)
    try:
        if len(item.text.encode('utf-16-le'))//2>2000:
            data=item.text.encode('utf-8')
            if len(data)>8*1024*1024:raise Invalid('Notification exceeds the attachment limit')
            outgoing['content']='Full notification attached.';outgoing['attachments']=[]
            response=httpx.request(method,url,headers={'Authorization':'Bot '+os.environ['DISCORD_BOT_TOKEN']},data={'payload_json':json.dumps(outgoing)},files={'files[0]':('notification.txt',data,'text/plain')},timeout=15)
        else:
            outgoing['attachments']=[]
            response=httpx.request(method,url,headers={'Authorization':'Bot '+os.environ['DISCORD_BOT_TOKEN']},json=outgoing,timeout=15)
        response.raise_for_status();message=response.json()
        with transaction.atomic():
            current=Outbox.objects.get(pk=item.pk)
            if current.status!='sending' or current.lease_until!=item.lease_until:
                return {'status':current.status}
            save(item.guild,'delivery',{'message_id':message['id'],'channel':item.channel},str(item.pk))
            status='sent' if current.channel==item.channel and payload_for(current)==payload else 'preview'
            Outbox.objects.filter(pk=item.pk).update(status=status,attempts=0,lease_until=None,retry_at=None,last_error='')
            if status=='sent' and item.key.startswith(f'{item.guild_id}:reminder:'):
                reminder=Record.objects.filter(guild_id=item.guild_id,kind='reminder',key=item.key.split(':',2)[2]).first()
                if reminder and reminder.data['status']!='cancelled':reminder.data['status']='sent';reminder.save()
        return {'status':status,'message_id':message['id']}
    except Exception as exc:
        status='uncertain';delay=min(300,2**min(item.attempts,8))
        if isinstance(exc,httpx.HTTPStatusError):
            code=exc.response.status_code
            status='retry' if code==429 or (code>=500 and previous) else 'uncertain' if code>=500 or code==408 else 'failed'
            if code==429:
                value=exc.response.headers.get('Retry-After',delay)
                try:value=exc.response.json().get('retry_after',value)
                except ValueError:pass
                try:delay=max(delay,min(3600,float(value)))
                except (KeyError,ValueError,TypeError):pass
        elif isinstance(exc,httpx.TransportError) and previous:status='retry'
        elif isinstance(exc,Invalid):status='failed'
        if status=='retry' and item.attempts>=6:status='failed'
        Outbox.objects.filter(pk=item.pk,status='sending',lease_until=item.lease_until).update(status=status,lease_until=None,retry_at=timezone.now()+timedelta(seconds=delay),last_error=f'{type(exc).__name__}: delivery {status}; check Discord permissions or reconcile the message')
        raise


def send_due(limit=100,stop_event=None):
    if os.getenv('ENABLE_DISCORD_DELIVERY')!='1':return {'sent':0,'failed':0}
    now=timezone.now();sent=failed=0
    Outbox.objects.filter(status='sending',lease_until__lte=now).update(status='uncertain',last_error='Worker stopped during delivery; reconcile the remote message')
    items=Outbox.objects.filter(status__in=['preview','retry'],channel__regex=r'^[0-9]+$').filter(Q(retry_at__isnull=True)|Q(retry_at__lte=now)).order_by('created','pk')
    for item in items[:limit]:
        if stop_event:
            if stop_event.is_set():break
            from guilds.health import heartbeat
            heartbeat('scheduler')
        try:result=deliver(item,True,queued=True);sent+=int(result['status']=='sent')
        except Exception:failed+=1
    return {'sent':sent,'failed':failed}
