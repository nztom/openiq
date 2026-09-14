"""Resolve a Discord send whose remote result could not be confirmed."""
import os
import httpx
from django.core.management.base import BaseCommand,CommandError
from django.db import transaction
from guilds.models import Outbox,Record
from guilds.modules.core import save


class Command(BaseCommand):
    help='Resolve an uncertain notification using a verified message ID or an operator-confirmed absent message.'

    def add_arguments(self,parser):
        parser.add_argument('id',type=int)
        choice=parser.add_mutually_exclusive_group(required=True)
        choice.add_argument('--message-id')
        choice.add_argument('--find',action='store_true',help='Find this bot’s marked message in bounded channel history, without sending anything.')
        choice.add_argument('--confirm-not-sent',action='store_true')

    def handle(self,*args,**options):
        item=Outbox.objects.get(pk=options['id'])
        if item.status not in ['uncertain','failed']:raise CommandError('Only uncertain or failed notifications can be reconciled')
        message_id=options['message_id']
        if message_id or options['find']:
            if (message_id and not message_id.isdecimal()) or not item.channel.isdecimal():raise CommandError('Use numeric message and channel IDs')
            token=os.getenv('DISCORD_BOT_TOKEN')
            if not token:raise CommandError('DISCORD_BOT_TOKEN is required to verify the remote message')
            headers={'Authorization':'Bot '+token}
            bot=httpx.get('https://discord.com/api/v10/users/@me',headers=headers,timeout=15);bot.raise_for_status()
            if options['find']:
                marker=f'OpenIQ delivery {item.guild_id}:{item.pk}'
                before=None
                for page in range(100):
                    params={'limit':100}
                    if before:params['before']=before
                    response=httpx.get(f'https://discord.com/api/v10/channels/{item.channel}/messages',headers=headers,params=params,timeout=15)
                    response.raise_for_status();messages=response.json()
                    matches=[m for m in messages if m.get('author',{}).get('id')==bot.json()['id'] and any(e.get('footer',{}).get('text')==marker for e in m.get('embeds',[]))]
                    if len(matches)>1:raise CommandError('Multiple matching messages; verify and supply --message-id')
                    if matches:message_id=str(matches[0]['id']);break
                    if len(messages)<100:raise CommandError('Delivery outcome is unresolved; inspect the channel before confirming absence')
                    before=messages[-1]['id']
                else:raise CommandError('Delivery history exceeds the reconciliation limit; supply a verified --message-id')
            message=httpx.get(f'https://discord.com/api/v10/channels/{item.channel}/messages/{message_id}',headers=headers,timeout=15);message.raise_for_status();data=message.json()
            if data['author']['id']!=bot.json()['id'] or str(data['channel_id'])!=item.channel:raise CommandError('Message was not sent by this bot in the expected channel')
        with transaction.atomic():
            current=Outbox.objects.select_for_update().get(pk=item.pk)
            if current.status not in ['uncertain','failed'] or current.channel!=item.channel:
                raise CommandError('Notification changed during reconciliation; inspect its current state')
            if message_id:save(item.guild,'delivery',{'message_id':message_id,'channel':item.channel},str(item.pk))
            else:Record.objects.filter(guild=item.guild,kind='delivery',key=str(item.pk)).delete()
            Outbox.objects.filter(pk=item.pk).update(status='preview',attempts=0,retry_at=None,lease_until=None,last_error='')
        self.stdout.write('Notification reconciled and queued for the next delivery pass.')
