import random,json
from .core import *
from guilds.models import Outbox
from .analytics import calculate

def preview(g,key,content,channel='preview'):
    obj,_=Outbox.objects.get_or_create(key=f'{g.pk}:{key}',defaults={'guild':g,'text':content,'channel':channel})
    if obj.text!=content or obj.channel!=channel:
        obj.text=content;obj.channel=channel
        if obj.status not in ['sending','uncertain']:obj.status='preview';obj.attempts=0;obj.retry_at=None;obj.last_error=''
        obj.save()
    return {'id':obj.pk,'text':obj.text,'status':obj.status}

def handle(g,action,p,role,user):
    if action=='reminder': return public(save(g,'reminder',{'user':user.pk,'text':text(p['text'],maximum=1500),'at':timestamp(p['at']),'status':'pending'}))
    if action=='cancel_reminder':
        r=get(g,'reminder',p['reminder'])
        if r.data['user']!=user.pk: raise PermissionDenied()
        Outbox.objects.filter(guild=g,key=f'{g.pk}:reminder:{r.key}').exclude(status__in=['sent','sending','uncertain']).update(status='cancelled',retry_at=None)
        r.data['status']='cancelled'; r.save(); return public(r)
    if action=='ticket': return public(save(g,'ticket',{'user':user.pk,'category':text(p.get('category','General')),'subject':text(p['subject']),'text':text(p['text'],maximum=5000),'status':'open','replies':[]}))
    if action=='reply':
        r=get(g,'ticket',p['ticket'])
        if role=='member' and r.data['user']!=user.pk: raise PermissionDenied()
        if r.data['status']!='open':raise Invalid('This ticket is closed')
        r.data['replies'].append({'by':user.username,'text':text(p['text'],maximum=5000),'at':now()}); r.save(); return public(r)
    if action=='apply':
        data={'user':user.pk,'family':text(p['family']),'answers':text(p['answers'],maximum=5000),'status':'pending'}
        if p.get('form'):
            form=get(g,'recruitment_form',p['form']);answers=p.get('responses')
            if not isinstance(answers,list) or len(answers)!=len(form.data['questions']):raise Invalid('Answer every application question')
            data.update(form=form.key,questions=form.data['questions'],responses=[text(answer,'answer',5000) for answer in answers])
        return public(save(g,'application',data))
    if action=='roll':
        result={'user':user.username,'roll':random.SystemRandom().randint(1,100),'at':now()}; save(g,'roll',result); return result
    if action=='tap':
        r=save(g,'minigame',{'level':0,'fails':0},str(user.pk)) if not Record.objects.filter(guild=g,kind='minigame',key=str(user.pk)).exists() else get(g,'minigame',user.pk)
        chance=max(0.05,0.8-r.data['level']*0.1)+min(r.data['fails']*0.01,0.15); success=random.SystemRandom().random()<chance
        r.data['level']+=int(success); r.data['fails']=0 if success else r.data['fails']+1; r.save(); return {**public(r),'success':success,'chance':chance,'mode':'local minigame rules'}
    if action=='summary_text':
        content=text(p['text'],maximum=20000); sentences=content.replace('\n','. ').split('. '); return {'summary':'. '.join(sentences[:5]),'mode':'local extractive summary'}
    if action=='roast':
        m=owner_or_self(g,role,user,p['member']); s=next(x for x in calculate(g)['members'] if x['id']==m.key); return {'text':f"{m.data['name']} has {s['deaths']} deaths. At least the respawn button knows a loyal customer.",'mode':'local template'}
    require(role)
    if action=='ticket_preview':
        from guilds.discord_tickets import plan
        return {'text':json.dumps(plan(g,get(g,'ticket',p['ticket'])),indent=2)}
    if action=='review_application':
        a=get(g,'application',p['application']); a.data.update(status=choice(p['status'],['accepted','rejected'],'status'),review=text(p['review'],maximum=3000),reviewer=user.username); a.save(); return public(a)
    if action in ['close_ticket','reopen_ticket']:
        t=get(g,'ticket',p['ticket']); t.data['status']='closed' if action=='close_ticket' else 'open'; t.save(); return public(t)
    if action=='welcome':
        member=get(g,'member',p['member']) if p.get('member') else None
        name=member.data['name'] if member else text(p['name'])
        result=preview(g,'welcome:'+member.key if member else ident(),f"Welcome {name}! {p.get('message','Choose a role and introduce yourself.')}",g.config.get('channels',{}).get('welcome','preview'))
        if member:
            from guilds.discord_welcome import components
            save(g,'message_components',{'components':components(g,member)},str(result['id']))
        return result
    if action=='weekly':
        from datetime import timedelta
        cutoff=(datetime.now(timezone.utc)-timedelta(days=7)).date().isoformat(); wars=[w for w in rows(g,'war') if cutoff<=w.data['date']<=now()[:10]]
        return preview(g,ident(),f"{g.name}: {len(wars)} wars in the past seven days. "+' | '.join(w.data['date']+' '+w.data['result'] for w in wars))
    if action in ['post_event','ping_missing']:
        e=get(g,'event',p['event']); names={m.key:m.data['name'] for m in rows(g,'member')}; signed={s['member'] for s in e.data['signups']}
        if action=='ping_missing': content='Awaiting response: '+', '.join(m.data['name'] for m in rows(g,'member') if m.data.get('active') and m.key not in signed)
        else: content=e.data['title']+' — '+e.data['at']+'\n'+('Archived' if e.data.get('archived') else 'Locked' if e.data.get('locked') else 'Signups open')+'\n'+'\n'.join(t['name']+f" (capacity {t['capacity']}): "+', '.join(names.get(s['member'],'Unknown')+(' (waitlist)' if s.get('waitlisted') else '') for s in e.data['signups'] if s['team']==t['name']) for t in e.data['teams'])
        result=preview(g,'event:'+e.key if action=='post_event' else ident(),content,g.config.get('channels',{}).get('events','preview'))
        if action=='post_event':
            from guilds.discord_components import event_components
            embed={'title':e.data['title'][:256]}
            if e.data.get('image'):embed['image']={'url':e.data['image']}
            if e.data.get('accent'):embed['color']=int(e.data['accent'][1:],16)
            payload={'components':event_components(g,e),'embeds':[embed]}
            old=Record.objects.filter(guild=g,kind='message_components',key=str(result['id'])).first()
            if old and old.data!=payload:Outbox.objects.filter(pk=result['id']).exclude(status__in=['sending','uncertain']).update(status='preview')
            save(g,'message_components',payload,str(result['id']))
        return result
    if action=='run_due':
        delivered=0
        for r in rows(g,'reminder'):
            if r.data['status']=='pending' and r.data['at']<=now():
                preview(g,'reminder:'+r.key,r.data['text'],g.config.get('channels',{}).get('reminders') or g.config.get('channels',{}).get('bot','preview')); r.data['status']='previewed'; r.save(); delivered+=1
        for milestone in g.config.get('milestones',[100,1000]):
            for s in calculate(g)['members']:
                if s['kills']>=milestone: preview(g,f"milestone:{s['id']}:{milestone}",f"{s['name']} reached {milestone} kills!")
        return {'reminders_processed':delivered}
    raise Invalid('Unknown community action')
