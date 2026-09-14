"""Welcome role buttons share a whitelist and require the intended member's access."""
import os
import httpx
from .modules.core import Invalid,owner_or_self,save
from .services import access,execute
from .discord_tickets import snowflake
from .models import Record


def role_context(server):
    headers={'Authorization':'Bot '+os.environ['DISCORD_BOT_TOKEN']}
    def read(path):
        response=httpx.get('https://discord.com/api/v10'+path,headers=headers,timeout=15)
        response.raise_for_status();return response.json()
    bot=read('/users/@me')
    membership=read(f'/guilds/{server}/members/{bot["id"]}')
    roles={str(r['id']):r for r in read(f'/guilds/{server}/roles')}
    owned=[r for key,r in roles.items() if key==server or key in membership['roles']]
    permissions=0
    for role in owned:permissions|=int(role['permissions'])
    if not permissions & ((1<<3)|(1<<28)):
        raise Invalid('The bot needs Manage Roles permission to update welcome roles.')
    return roles,max((r['position'] for r in owned),default=0)


def manageable(roles,highest,server,role_id):
    role=roles.get(role_id)
    if not role or role_id==server or role.get('managed') or role['position']>=highest:
        raise Invalid('Welcome roles must exist, be unmanaged, and sit below the bot’s highest role.')

def components(g,member):
    from .discord_components import signed_id
    roles=g.config.get('welcome',{}).get('role_ids',{})
    buttons=[{'type':2,'style':1,'label':str(label)[:80],'custom_id':signed_id('welcome',g,member.key,snowflake(role_id,'welcome role ID'))} for label,role_id in list(roles.items())[:25]]
    return [{'type':1,'components':buttons[i:i+5]} for i in range(0,len(buttons),5)]

def choose(user,g,member_key,role_id,enabled=False):
    member=owner_or_self(g,access(user,g),user,member_key)
    config=g.config.get('welcome',{});roles=config.get('role_ids',{})
    label=next((label for label,value in roles.items() if str(value)==str(role_id)),None)
    if label is None:
        raise Invalid('This welcome role is no longer available')
    if label not in config.get('roles',['Raider','Social']):
        raise Invalid('This role is not enabled for welcome selection')
    if enabled:
        if os.getenv('ENABLE_DISCORD_DELIVERY')!='1' or not os.getenv('DISCORD_BOT_TOKEN'):
            raise Invalid('Discord delivery is not enabled')
        server=snowflake(g.server_id,'server ID');target=snowflake(member.data.get('discord_id'),'member account link');role_id=snowflake(role_id,'welcome role ID')
        available,highest=role_context(server)
        manageable(available,highest,server,role_id)
        prior=Record.objects.filter(guild=g,kind='welcome_delivery',key=member.key).first()
        granted=set(prior.data.get('roles',[]) if prior else [])
        obsolete=granted-{role_id} if config.get('replace_selection') else set()
        for old in obsolete:
            if old in available:manageable(available,highest,server,old)
        headers={'Authorization':'Bot '+os.environ['DISCORD_BOT_TOKEN']}
        try:
            response=httpx.put(f'https://discord.com/api/v10/guilds/{server}/members/{target}/roles/{role_id}',headers=headers,timeout=15)
            response.raise_for_status()
            for old in sorted(obsolete):
                if old not in available:continue
                response=httpx.delete(f'https://discord.com/api/v10/guilds/{server}/members/{target}/roles/{old}',headers=headers,timeout=15)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code==403:
                raise Invalid('Discord denied the welcome role update. Check Manage Roles and move the bot role above the selected roles, then retry.') from exc
            raise
        save(g,'welcome_delivery',{'roles':sorted((granted|{role_id})-obsolete)},member.key)
    result=execute(user,g.pk,'operations','welcome_role',{'member':member.key,'role':label})
    return {**result,'delivery':'Discord' if enabled else 'local'}
