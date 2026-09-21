"""Typed slash schemas built from the shared domain action catalog."""
import inspect
import json
import keyword

import discord
from discord import app_commands
from asgiref.sync import sync_to_async
from .catalog import ACTIONS, f, MEM, WAR, EVENT
from .modules.commands import ALIASES, COMMANDS
from .modules.core import Invalid
from .models import Guild, Record
from .discord_auth import role_for

EXTRA_FIELDS = {
    'event edit':[f('id','Event','event'),f('title','Title'),f('locked','Lock signups','checkbox'),f('archived','Archive event','checkbox')],
    'event signup':[EVENT,f('team','Team name; leave blank to withdraw',default='')],
    'trends':[MEM], 'warlog':[WAR], 'gear':[MEM], 'whois':[f('discord_id','Discord account')],
    'exception':[MEM], 'removeexception':[MEM], 'unlink':[MEM], 'unlink-twitch':[MEM], 'reset-class':[MEM],
    'setbotchannel':[f('channel','Command channel')], 'setsyncnotifications':[f('channel','Sync notification channel')],
    'seteventlog':[f('channel','Event channel')], 'setup':[f('names','Reviewed family names separated by commas or newlines','lines')],
    'configweeklysummary':[f('enabled','Enable summary','checkbox',default=True),f('weekday','Monday 0 to Sunday 6','number',default=0),f('hour','Hour 0 to 23','number',default=20),f('channel','Summary channel')],
    'config':[f('setting','Configuration section','select',['roles','channels','welcome','tickets','weekly','sync','command_permissions']), f('value','JSON value for this configuration section')],
}
REFERENCE_TYPES={'member','war','event','assignment','reminder'}


def schema(command):
    target=ALIASES.get(command)
    action=next((a for a in ACTIONS if (a['module'],a['action'])==target),None)
    fields=EXTRA_FIELDS.get(command, action['fields'] if action else [])
    if command=='setclass':fields=[field for field in fields if field['name']!='member']
    if command=='link':fields=[field for field in fields if field['name']!='user_id']
    return fields, action['label'] if action else command.replace('-',' ').capitalize()


def option_name(name):
    return name+'_name' if keyword.iskeyword(name) else name


def annotation(field):
    if field['name']=='discord_id':return discord.Member
    if field['name']=='channel':return discord.TextChannel
    if field['type']=='checkbox':return bool
    if field['type']=='number':return int
    return str


def normalize(command, supplied):
    fields,_=schema(command);result={}
    for field in fields:
        value=supplied.get(option_name(field['name']),field.get('default'))
        if value is None:continue
        if field['type']=='teams':
            teams=[]
            for line in value.splitlines():
                parts=line.split(',')
                if len(parts) not in [2,3]:raise Invalid('Teams use name,capacity,optional group on each line')
                try:capacity=int(parts[1])
                except ValueError:raise Invalid('Team capacity must be a whole number')
                teams.append({'name':parts[0].strip(),'capacity':capacity,'group':parts[2].strip() if len(parts)==3 else ''})
            value=teams
        if field['type']=='lines':value=[part.strip() for part in value.replace(',', '\n').splitlines() if part.strip()]
        if field['name'] in ['channel','discord_id']:value=str(value.id)
        result[field['name']]=value
    if command=='config':
        try:value=json.loads(result['value'])
        except (ValueError,KeyError):raise Invalid('Provide a valid JSON value for the selected setting')
        if not isinstance(value,dict):raise Invalid('The selected setting requires a JSON object')
        return {'config':{result['setting']:value}}
    return result


def autocomplete_choices(kind,interaction,current):
    if interaction.guild is None:return []
    from django.contrib.auth.models import User
    account=User.objects.filter(username='discord_'+str(interaction.user.id)).values_list('is_active',flat=True).first()
    if account is False:return []
    servers=Guild.objects.filter(server_id=str(interaction.guild_id))
    selected=getattr(interaction.namespace,'guild_name','')
    if selected:servers=servers.filter(name__iexact=selected)
    allowed=[]
    for guild in servers:
        tier=role_for(guild,{'owner':interaction.guild.owner_id==interaction.user.id,'permissions':str(interaction.user.guild_permissions.value)},[r.id for r in interaction.user.roles])
        if tier and (kind!='assignment' or tier!='member'):allowed.append(guild)
    if kind=='guild':return [app_commands.Choice(name=g.name[:100],value=g.name) for g in allowed if current.casefold() in g.name.casefold()][:25]
    if len(allowed)!=1:return []
    result=[]
    uid=User.objects.filter(username='discord_'+str(interaction.user.id)).values_list('pk',flat=True).first()
    for record in Record.objects.filter(guild=allowed[0],kind=kind).order_by('-created'):
        if kind=='reminder' and record.data.get('user')!=uid:continue
        label=str(record.data.get('name') or record.data.get('title') or record.data.get('text') or record.data.get('date') or record.key)
        if current.casefold() in label.casefold():result.append(app_commands.Choice(name=label[:100],value=record.key))
        if len(result)==25:return result
    return result


def autocomplete(kind):
    async def complete(interaction, current):
        return await sync_to_async(autocomplete_choices)(kind,interaction,current)
    return complete


def build_command(name, run):
    fields,description=schema(name)
    async def callback(interaction, **values):
        await run(interaction, name, values, values.get('guild_name',''))
    parameters=[inspect.Parameter('interaction',inspect.Parameter.POSITIONAL_OR_KEYWORD,annotation=discord.Interaction)]
    descriptions={};choices={};completions={}
    for field in fields:
        option=option_name(field['name']);default=field.get('default')
        optional=default is not None or field['type']=='checkbox' or field['name'] in ['message','backfill','image','accent'] or (name in ['gear','whois','reset-class','sync roster']) or (name=='event edit' and field['name']!='id')
        parameters.append(inspect.Parameter(option,inspect.Parameter.KEYWORD_ONLY,annotation=annotation(field),default=default if optional else inspect.Parameter.empty))
        descriptions[option]=field['label'][:100]
        if field.get('options'):choices[option]=[app_commands.Choice(name=value,value=value) for value in field['options']]
        if field['type'] in REFERENCE_TYPES:completions[option]=autocomplete(field['type'])
    parameters.append(inspect.Parameter('guild_name',inspect.Parameter.KEYWORD_ONLY,annotation=str,default=''))
    descriptions['guild_name']='BDO guild, needed only when this server hosts multiple guilds'
    completions['guild_name']=autocomplete('guild')
    callback.__signature__=inspect.Signature(parameters)
    callback=app_commands.describe(**descriptions)(callback)
    callback=app_commands.choices(**choices)(callback)
    callback=app_commands.autocomplete(**completions)(callback)
    return app_commands.Command(name=name.split(' ')[-1],description=description[:100],callback=callback)
