from collections import defaultdict
from .core import *

def handle(g,action,p,role,user):
    require(role)
    if action=='start':
        return public(save(g,'session',{'title':text(p['title']),'started':now(),'status':'live','events':[],'public':False}))
    s=get(g,'session',p['session'])
    if action=='import_log':
        from .logformat import parse_log
        return handle(g,'ingest',{'session':s.key,'events':parse_log(text(p['text'],'log',1000000),p['date'],p.get('offset','+00:00'))},role,user)
    if action=='ingest':
        if s.data['status']!='live':
            raise Invalid('Session is stopped')
        events=p.get('events',[])
        if not isinstance(events,list) or len(events)>2000:
            raise Invalid('At most 2000 events per batch')
        seen={e['id'] for e in s.data['events']}; added=0
        for raw in events:
            eid=text(raw['id'],'event ID',160)
            if eid in seen: continue
            e={'id':eid,'at':timestamp(raw['at']),'kind':choice(raw['kind'],['kill','death'],'event kind'),'player':text(raw['player'],'player',80),'target':text(raw['target'],'target',80),'guild':text(raw.get('guild','Unknown'),'enemy guild',80),'class':str(raw.get('class','Unknown'))[:40],'family':str(raw.get('family',''))[:80]}
            s.data['events'].append(e); seen.add(eid); added+=1
        s.data['events'].sort(key=lambda e:e['at']); s.save(); return {'added':added,'total':len(seen)}
    if action=='stop': s.data.update(status='saved',ended=now())
    elif action=='share': s.data.update(public=bool(p.get('public')),share_token=s.data.get('share_token') or ident())
    elif action=='link':
        w=get(g,'war',p['war'])
        previous_war=Record.objects.filter(guild=g,kind='war',key=s.data.get('war')).first()
        if previous_war and previous_war.data.get('session')==s.key:previous_war.data.pop('session');previous_war.save()
        previous_session=Record.objects.filter(guild=g,kind='session',key=w.data.get('session')).first()
        if previous_session and previous_session.data.get('war')==w.key:previous_session.data.pop('war');previous_session.save()
        w.data['session']=s.key; w.save(); s.data['war']=w.key
    else: raise Invalid('Unknown live action')
    s.save(); return public(s)

def summarize(s):
    if not s.data.get('events') and s.data.get('retained_summary'):
        return s.data['retained_summary']
    enemies=defaultdict(lambda:{'kills':0,'deaths':0,'players':{},'classes':{}}); buckets=defaultdict(lambda:{'kills':0,'deaths':0}); k=d=0
    for e in s.data['events']:
        field='kills' if e['kind']=='kill' else 'deaths'; k+=field=='kills'; d+=field=='deaths'; en=enemies[e['guild']]; en[field]+=1; name=e['target'] if e['kind']=='kill' else e['player']; en['players'].setdefault(name,{'kills':0,'deaths':0})[field]+=1; en['classes'][e['class']]=en['classes'].get(e['class'],0)+1; buckets[e['at'][:16]][field]+=1
    return {'kills':k,'deaths':d,'kdr':kdr(k,d),'enemies':dict(enemies),'timeline':[{'at':at,**v} for at,v in sorted(buckets.items())]}
