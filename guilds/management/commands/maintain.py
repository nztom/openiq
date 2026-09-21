"""Explicit, scoped maintenance operations for guild owners and operators."""
import json,time
from datetime import timedelta
from pathlib import Path
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand,CommandError
from django.db import transaction
from django.utils import timezone
from guilds.models import Guild,Access,Record,Audit,Outbox
from guilds.services import access,execute
from guilds.modules.core import require
from guilds.portability import export_guild


class Command(BaseCommand):
    help='Export/delete a guild, remove a user, relink Discord, or clean expired tokens and old audit/outbox rows.'
    def add_arguments(self,parser):
        parser.add_argument('operation',choices=['export','delete_guild','remove_user','relink_discord','cleanup'])
        parser.add_argument('--guild',type=int,required=True);parser.add_argument('--actor',required=True)
        parser.add_argument('--username');parser.add_argument('--member');parser.add_argument('--discord-id')
        parser.add_argument('--output',type=Path);parser.add_argument('--days',type=int,default=90)
        parser.add_argument('--apply',action='store_true');parser.add_argument('--confirmation')

    @transaction.atomic
    def handle(self,*args,**options):
        guild=Guild.objects.select_for_update().get(pk=options['guild']);actor=User.objects.get(username=options['actor']);require(access(actor,guild),'owner')
        operation=options['operation']
        if operation=='export':
            if not options['output']:raise CommandError('Export requires --output')
            package=export_guild(guild)
            with options['output'].open('x',encoding='utf-8') as stream:
                options['output'].chmod(0o600);json.dump(package,stream,indent=2,default=str)
            self.stdout.write(str(options['output']));return
        if options['days']<1:raise CommandError('days must be positive')
        if not options['apply']:
            self.stdout.write(json.dumps({'operation':operation,'guild':guild.pk,'applied':False,'next':'Review the operation and rerun with --apply'}));return
        if operation=='delete_guild':
            execute(actor,guild.pk,'admin','disband',{'confirmation':options['confirmation']})
            self.stdout.write('Guild deleted.');return
        if operation=='remove_user':
            target=User.objects.select_for_update().get(username=options['username'])
            membership=Access.objects.get(guild=guild,user=target)
            if membership.role=='owner' and Access.objects.filter(guild=guild,role='owner').count()==1:raise CommandError('Assign another owner before removing the last owner')
            membership.delete()
            for member in Record.objects.filter(guild=guild,kind='member'):
                if str(member.data.get('user_id'))==str(target.pk):member.data.update(user_id='',discord_id='');member.save()
            for token in Record.objects.filter(guild=guild,kind='capture_token'):
                if token.data.get('user')==target.pk:token.delete()
            for session in Session.objects.all():
                if session.get_decoded().get('_auth_user_id')==str(target.pk):session.delete()
            if not Access.objects.filter(user=target).exists() and not target.is_staff and not target.is_superuser:target.delete()
        elif operation=='relink_discord':
            if not options['discord_id'] or not options['discord_id'].isdecimal():raise CommandError('A numeric --discord-id is required')
            target=User.objects.select_for_update().get(username=options['username'])
            if not Access.objects.filter(guild=guild,user=target).exists():raise CommandError('The target user must belong to this guild')
            execute(actor,guild.pk,'roster','link',{'member':options['member'],'user_id':target.pk,'discord_id':options['discord_id']})
        else:  # The remaining parser choice is cleanup.
            cutoff=timezone.now()-timedelta(days=options['days'])
            for token in Record.objects.filter(guild=guild,kind__in=['capture_token','adoption']):
                expiry=token.data.get('expires',0 if token.kind=='capture_token' else '')
                if (token.kind=='capture_token' and expiry<=time.time()) or (token.kind=='adoption' and expiry<timezone.now().isoformat()):token.delete()
            Audit.objects.filter(guild=guild,created__lt=cutoff).delete()
            expired=Outbox.objects.filter(guild=guild,status__in=['sent','cancelled'],created__lt=cutoff)
            keys=[str(pk) for pk in expired.values_list('pk',flat=True)]
            Record.objects.filter(guild=guild,kind__in=['delivery','delivery_retry','delivery_pending','message_components'],key__in=keys).delete();expired.delete()
            Record.objects.filter(guild=guild,kind='bot_receipt',created__lt=cutoff).delete()
        Audit.objects.create(guild=guild,actor=actor.username,action='maintenance.'+operation,data={'username':options['username']})
        self.stdout.write(json.dumps({'operation':operation,'guild':guild.pk,'applied':True}))
