"""Scheduled work and configuration workflows, all local until delivery is enabled."""
from datetime import timedelta
from zoneinfo import ZoneInfo
from .core import *
from .community import preview
from .analytics import calculate

def handle(g,action,p,role,user,sources=None):
    if action in ['challenge','accept_challenge']:
        import secrets
        if action=='challenge':
            opponent=get(g,'member',p['opponent'])
            if not opponent.data.get('user_id'):raise Invalid('Choose an opponent linked to an account')
            if str(opponent.data['user_id'])==str(user.pk):raise Invalid('Choose another player')
            return public(save(g,'challenge',{'challenger':user.username,'challenger_id':user.pk,'opponent':opponent.data['name'],'opponent_id':str(opponent.data['user_id']),'roll':secrets.randbelow(100)+1,'status':'pending'}))
        challenge=get(g,'challenge',p['challenge'])
        if str(user.pk)!=challenge.data['opponent_id']:raise PermissionDenied('Only the challenged player can accept')
        if challenge.data['status']!='pending':raise Invalid('Challenge already completed')
        other=secrets.randbelow(100)+1;mine=challenge.data['roll']
        challenge.data.update(opponent_roll=other,status='complete',winner=challenge.data['challenger'] if mine>other else challenge.data['opponent'] if other>mine else 'Draw');challenge.save();return public(challenge)
    if action=='welcome_role':
        member=owner_or_self(g,role,user,p['member']);allowed=g.config.get('welcome',{}).get('roles',['Raider','Social']);selected=choice(p['role'],allowed,'welcome role')
        member.data.setdefault('community_roles',[])
        if g.config.get('welcome',{}).get('replace_selection'):member.data['community_roles']=[]
        if selected not in member.data['community_roles']:member.data['community_roles'].append(selected)
        member.save();return public(member)
    require(role)
    if action=='schedule':
        require(role,'owner');kind=choice(p['kind'],['weekly','sync'],'schedule')
        g.config[kind]={**g.config.get(kind,{}),'enabled':bool(p.get('enabled',True)),'weekday':integer(p.get('weekday',0),'weekday',0,6),'hour':integer(p.get('hour',20),'hour',0,23),'timezone':text(p.get('timezone','Pacific/Auckland')),'channel':str(p.get('channel','preview'))}
        try:ZoneInfo(g.config[kind]['timezone'])
        except Exception:raise Invalid('Invalid timezone')
        g.save();return g.config[kind]
    if action in ['tick','catchup']:
        from .community import handle as community
        community(g,'run_due',{},role,user)
        at=datetime.fromisoformat(timestamp(p.get('at',now())))
        count=0
        from .events import handle as events
        for event in rows(g,'event'):
            if event.data.get('recurrence_days') and not event.data.get('next_event') and event.data['at']<=at.isoformat():
                events(g,'next',{'event':event.key},role,user); count+=1
        for kind,key,day,at,config in due_jobs(g,action,p):
            if kind=='weekly':
                start=(day-timedelta(days=7)).isoformat();end=day.isoformat();wars=[w for w in rows(g,'war') if start<w.data['date']<=end]
                preview(g,key,f'{g.name}: {len(wars)} wars for week ending {end}.',config.get('channel','preview'))
                status='previewed'
            else:
                names=g.config.get('sync_fixture')
                if config.get('url'):
                    if sources is None or config['url'] not in sources:
                        raise Invalid('Roster synchronization requires prepared source data')
                    names,error=sources[config['url']]
                    if error:
                        save(g,'job',{'type':kind,'at':at.isoformat(),'status':'source_error','message':error},key);count+=1;continue
                if names:
                    from .roster import handle as roster
                    roster(g,'sync',{'names':names},role,user);status='fixture_synced'
                else:status='needs_roster_source'
            save(g,'job',{'type':kind,'at':at.isoformat(),'status':status},key);count+=1
        return {'processed':count}
    if action=='recruitment_form':
        require(role,'owner');questions=p.get('questions',[])
        if not isinstance(questions,list) or not 1<=len(questions)<=20:raise Invalid('Supply 1–20 application questions')
        return public(save(g,'recruitment_form',{'title':text(p['title']),'questions':[text(q,'question',500) for q in questions],'channel':str(p.get('channel','preview'))},p.get('id')))
    if action=='ticket_category':
        require(role,'owner');return public(save(g,'ticket_category',{'name':text(p['name']),'staff_role':str(p.get('staff_role',''))},p.get('id')))
    raise Invalid('Unknown operations action')


def due_jobs(g,action,p):
    at=datetime.fromisoformat(timestamp(p.get('at',now())))
    days=integer(p.get('days',14 if action=='catchup' else 0),'lookback',0,90)
    for kind in ['weekly','sync']:
        config=g.config.get(kind,{})
        if not config.get('enabled'):continue
        local=at.astimezone(ZoneInfo(config.get('timezone','Pacific/Auckland')))
        for offset in range(days+1):
            day=local.date()-timedelta(days=offset)
            if day.weekday()!=config.get('weekday',0) or (offset==0 and local.hour<config.get('hour',20)):continue
            key=kind+':'+day.isoformat()
            if Record.objects.filter(guild=g,kind='job',key=key).exists():continue
            yield kind,key,day,at,config
