"""Discord-compatible command names, also executable locally for fixture tests."""
from .core import *
from .analytics import calculate
from .gear import current
from .community import preview
from guilds.models import Guild, Access

ALIASES={
 'event create':('events','save'),'event edit':('events','save'),'event signup':('events','signup'),
 'event post':('community','post_event'),'event next':('events','next'),
 'sync roster':('roster','sync'),'warscores':('wars','review'),'warscores-beta':('wars','review'),
 'vacation':('roster','vacation'),'link':('roster','link'),'class':('roster','class'),'setclass':('roster','class'),
 'gearupdate':('gear','save'),'deletegear':('gear','delete'),'link-twitch':('integrations','twitch_link'),
 'weeklysummary':('community','weekly'),'catchup-summaries':('operations','catchup'),
 'unsigned ping':('community','ping_missing'),'unsigned message':('community','ping_missing'),
 'performance-flags notify':('coaching','notify'),'config':('admin','settings'),'purgestats':('admin','purge'),
 'adopt':('admin','adopt'),'welcome':('community','welcome'),'reminder set':('community','reminder'),
 'reminder cancel':('community','cancel_reminder'),'roll':('community','roll'),'roast':('ai','roast'),
 'tap':('community','tap'),'notreadingallthat':('ai','summary'),
}
READ=['guildstats','warlog','trends','gear','gearlist','rankings','whois','unlinked','twitch-links','performance-flags list','retention','help','reminder list','sync-status','reload-commands','redeploy-slash-commands','cancel']
EXTRA=['exception','removeexception','unlink','unlink-twitch','reset-class','gearping','setbotchannel','setsyncnotifications','seteventlog','configweeklysummary','setup']
COMMANDS=sorted(set(ALIASES)|set(READ)|set(EXTRA))


def minimum_role(command):
    from guilds.catalog import ACTIONS
    if command in ALIASES:
        module,action=ALIASES[command]
        item=next((item for item in ACTIONS if item['module']==module and item['action']==action),None)
        if item:return item['role']
    if command in ['reload-commands','redeploy-slash-commands']:return 'owner'
    if command in ['unlinked','performance-flags list','retention','sync-status','exception','removeexception','unlink','gearping','setbotchannel','setsyncnotifications','seteventlog','configweeklysummary','setup']:return 'admin'
    return 'member'

def dispatch(g,command,p,role,user):
    from .registry import MODULES
    if command not in COMMANDS: raise Invalid('Unknown command')
    require(role,minimum_role(command))
    minimum=g.config.get('command_permissions',{}).get(command)
    if minimum: require(role,minimum)
    if command in ALIASES:
        module,action=ALIASES[command]
        if command=='event signup':
            m=own_member(g,user)
            if not m:raise Invalid('Link your member first')
            p={**p,'member':m.key}
        if command=='setclass':
            m=own_member(g,user)
            if not m: raise Invalid('Link your member first')
            p={**p,'member':m.key}
        if command=='sync roster' and 'names' not in p:
            raise Invalid('Use the shared service to prepare roster synchronization')
        return MODULES[module].handle(g,action,p,role,user)
    if command=='help':return {'commands':COMMANDS}
    if command=='guildstats':return calculate(g)['totals']
    if command=='trends':return next((s for s in calculate(g)['members'] if s['id']==p.get('member')), {})
    if command=='warlog':return public(get(g,'war',p['war']))
    if command=='gearlist':return {'gear':current(g)}
    if command=='rankings':
        from .gear import rankings
        return {'rankings':rankings(g)}
    if command=='gear':
        member=p.get('member') or (own_member(g,user).key if own_member(g,user) else '')
        return {'gear':next((r for r in current(g) if r['member']==member),None)}
    if command=='whois':
        found=[public(m) for m in rows(g,'member') if (p.get('discord_id') and str(m.data.get('discord_id'))==str(p['discord_id'])) or str(m.data.get('user_id'))==str(p.get('user_id',user.pk))]
        if role=='member':
            for member in found:member.pop('notes',None)
        return {'members':found}
    if command=='unlinked':require(role);return {'members':[m.data['name'] for m in rows(g,'member') if m.data.get('active') and not m.data.get('discord_id')]}
    if command=='twitch-links':return {'links':{m.data['name']:m.data['twitch'] for m in rows(g,'member') if m.data.get('twitch')}}
    if command=='performance-flags list':
        require(role);from .coaching import flags
        return {'flags':flags(g)}
    if command=='retention':require(role);return {'history':[public(r) for r in rows(g,'retention')]}
    if command=='reminder list':return {'reminders':[public(r) for r in rows(g,'reminder') if r.data['user']==user.pk]}
    if command=='sync-status':return {'configuration':g.config.get('sync',{}),'runs':[public(r) for r in rows(g,'job')]}
    if command in ['reload-commands','redeploy-slash-commands']:
        require(role,'owner');return {'registered_locally':COMMANDS,'delivery':'Use runbot --sync to register remotely; this preview makes no network writes.'}
    if command=='cancel':
        n=0
        for r in rows(g,'import'):
            if r.data.get('created_by')==user.pk and r.data['status']=='review':r.data['status']='cancelled';r.save();n+=1
        return {'cancelled':n}
    if command in ['exception','removeexception']:
        require(role);return MODULES['roster'].handle(g,'save',{'id':p['member'],'exception':command=='exception'},role,user)
    if command=='unlink':require(role);return MODULES['roster'].handle(g,'link',{'member':p['member'],'user_id':'','discord_id':''},role,user)
    if command=='unlink-twitch':return MODULES['integrations'].handle(g,'twitch_link',{'member':p['member'],'handle':''},role,user)
    if command=='reset-class':
        member=p.get('member') or (own_member(g,user).key if own_member(g,user) else '')
        if not member:raise Invalid('Link your member first')
        return MODULES['roster'].handle(g,'class',{'member':member,'class':'Unknown','spec':'Succession'},role,user)
    if command=='gearping':
        require(role);submitted={x['member'] for x in current(g)}
        return preview(g,ident(),'Missing gear: '+', '.join(m.data['name'] for m in rows(g,'member') if m.data.get('active') and m.key not in submitted))
    if command in ['setbotchannel','setsyncnotifications','seteventlog']:
        require(role);key={'setbotchannel':'bot','setsyncnotifications':'sync','seteventlog':'events'}[command];g.config.setdefault('channels',{})[key]=str(p.get('channel',''));g.save();return g.config['channels']
    if command=='configweeklysummary':
        require(role);g.config['weekly']={'enabled':bool(p.get('enabled',True)),'weekday':integer(p.get('weekday',0),'weekday',0,6),'hour':integer(p.get('hour',20),'hour',0,23),'channel':str(p.get('channel','preview'))};g.save();return g.config['weekly']
    if command=='setup':
        require(role);return MODULES['roster'].handle(g,'sync',p,role,user)
    raise Invalid('Command is not implemented')

def handle(g,action,p,role,user):
    if action!='run':raise Invalid('Unknown command action')
    return dispatch(g,text(p['command'],'command',80).lstrip('/'),p.get('arguments',{}),role,user)
