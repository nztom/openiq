"""Read-only Discord installation checks; never register commands or send messages."""
import json
import os
import httpx
from django.core.management.base import BaseCommand,CommandError
from guilds.models import Guild
from guilds.modules.commands import COMMANDS


def permissions_for(server,roles,membership,channel=None):
    owned={server,*map(str,membership.get('roles',[]))}
    permissions=0
    for role in roles:
        if str(role['id']) in owned:permissions|=int(role['permissions'])
    if permissions & 8:
        return (1<<64)-1
    if channel:
        overwrites=channel.get('permission_overwrites',[])
        for group in ([o for o in overwrites if str(o['id'])==server],
                      [o for o in overwrites if o['type']==0 and str(o['id']) in owned-{server}],
                      [o for o in overwrites if o['type']==1 and str(o['id'])==str(membership['user']['id'])]):
            allow=deny=0
            for overwrite in group:allow|=int(overwrite['allow']);deny|=int(overwrite['deny'])
            permissions=(permissions & ~deny)|allow
    return permissions


class Command(BaseCommand):
    help='Check Discord token, installation, roles, channels, intents and commands using GET requests only.'

    def add_arguments(self,parser):parser.add_argument('--guild',type=int)

    def handle(self,*args,**options):
        token=os.getenv('DISCORD_BOT_TOKEN')
        if not token:
            raise CommandError('Set DISCORD_BOT_TOKEN to run read-only bot diagnostics.')
        reports=[]
        with httpx.Client(base_url='https://discord.com/api/v10',headers={'Authorization':'Bot '+token},timeout=15) as client:
            def read(path):
                response=client.get(path);response.raise_for_status();return response.json()
            try:
                bot=read('/users/@me');application=read('/oauth2/applications/@me')
            except httpx.HTTPError:
                raise CommandError('Cannot verify the bot token/application. Check credentials and connectivity; no changes were made.') from None
            guilds=Guild.objects.all()
            if options['guild'] is not None:guilds=guilds.filter(pk=options['guild'])
            if not guilds.exists():
                raise CommandError('No configured guilds match this request.')
            for guild in guilds:
                checks={'token':True,'intents':{'guilds':True,'privileged_intents_required':False}}
                try:
                    server=str(guild.server_id)
                    if not server.isdecimal():
                        raise ValueError('Configure a numeric Discord server ID.')
                    read('/guilds/'+server);checks['installed']=True
                    membership=read(f'/guilds/{server}/members/{bot["id"]}')
                    roles=read(f'/guilds/{server}/roles')
                    channels={str(c['id']):c for c in read(f'/guilds/{server}/channels')}
                    owned={server,*map(str,membership['roles'])}
                    highest=max((r['position'] for r in roles if str(r['id']) in owned),default=0)
                    role_map={str(r['id']):r for r in roles}
                    checks['welcome_roles']={}
                    base=permissions_for(server,roles,membership)
                    for label,role_id in guild.config.get('welcome',{}).get('role_ids',{}).items():
                        role=role_map.get(str(role_id))
                        checks['welcome_roles'][label]=bool(base & (1<<28) and role and str(role_id)!=server and not role.get('managed') and role['position']<highest)
                    checks['channels']={}
                    for name,channel_id in guild.config.get('channels',{}).items():
                        if not channel_id:continue
                        channel=channels.get(str(channel_id))
                        bits=permissions_for(server,roles,membership,channel) if channel else 0
                        checks['channels'][name]={label:bool(bits & bit) for label,bit in [('view',1<<10),('send',1<<11),('embed',1<<14),('history',1<<16)]}
                    checks['ticket_channel_creation']=bool(base & (1<<4))
                    target=os.getenv('DISCORD_SYNC_GUILD','').strip()
                    path=f'/applications/{application["id"]}'
                    if target:path+=f'/guilds/{target}'
                    registered={c['name'] for c in read(path+'/commands')}
                    expected={c.split(' ')[0] for c in COMMANDS}
                    checks['missing_commands']=sorted(expected-registered)
                except (httpx.HTTPError,ValueError,KeyError,TypeError):
                    checks['error']='Installation checks failed. Verify server ID, bot installation, permissions and connectivity.'
                reports.append({'guild':guild.pk,'checks':checks})
        self.stdout.write(json.dumps({'read_only':True,'guilds':reports},indent=2))
