import secrets,hashlib
from datetime import timedelta
from django.contrib.auth.models import User
from guilds.models import Guild, Access, Record
from .core import *

def handle(g,action,p,role,user):
    require(role,'owner')
    if action=='settings':
        config=p.get('config')
        if not isinstance(config,dict): raise Invalid('Configuration must be an object')
        allowed={'channels','roles','command_permissions','weekly','sync','welcome','tickets','recruitment','milestones','alliance_mode','embed_color','retention','capture','integrations'}
        from guilds.settings_validation import validate
        validate(config,g.server_id)
        if 'retention' in config:
            retention=config['retention']
            if not isinstance(retention,dict) or set(retention)-{'capture_days','import_days','recap_days','summary_days'}:raise Invalid('Unknown retention setting')
            for key,value in retention.items():
                if isinstance(value,bool) or not isinstance(value,int) or not 0<=value<=36500:raise Invalid('Retention days must be integers from 0 to 36500')
        if set(config)-allowed: raise Invalid('Unknown setting: '+', '.join(set(config)-allowed))
        g.config.update(config); g.save(); return g.config
    if action=='access':
        try: target=User.objects.get(username=p['username'])
        except User.DoesNotExist: raise Invalid('User does not exist')
        tier=choice(p['role'],['owner','admin','member'],'role')
        if target==user and tier!='owner' and Access.objects.filter(guild=g,role='owner').count()==1: raise Invalid('Assign another owner before demoting yourself')
        Access.objects.update_or_create(guild=g,user=target,defaults={'role':tier}); return {'username':target.username,'role':tier}
    if action=='adoption_key':
        token=secrets.token_urlsafe(24); save(g,'adoption',{'token_hash':hashlib.sha256(token.encode()).hexdigest(),'issued_by':user.username,'used':False,'expires':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()},'current'); return {'key':token}
    if action=='adopt':
        from django.conf import settings
        if not settings.ALLOW_LOCAL_LOGIN:raise Invalid('Use the Discord-verified recovery endpoint to move a guild')
        r=get(g,'adoption','current')
        if r.data['used'] or r.data.get('expires','')<now() or not secrets.compare_digest(r.data.get('token_hash',''),hashlib.sha256(str(p['key']).encode()).hexdigest()): raise Invalid('Invalid adoption key')
        g.server_id=text(p['server_id']); g.save(); r.data['used']=True; r.save(); return {'server_id':g.server_id}
    if action=='disband':
        if p.get('confirmation')!=g.name: raise Invalid('Type the guild name to confirm')
        from .alliances import visible
        for alliance in visible(g): alliance.data['status']='disbanded'; alliance.save()
        guild_id=g.pk; g.delete(); return {'deleted_guild':guild_id}
    if action=='purge':
        if p.get('confirmation')!=g.name: raise Invalid('Type the guild name to confirm')
        count,_=Record.objects.filter(guild=g,kind__in=['war','import','session','assignment']).delete(); return {'deleted':count}
    raise Invalid('Unknown administrative action')
