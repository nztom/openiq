from .core import *

MEMBER_TEXT_FIELDS={'character':80,'class':40,'group':80}
MEMBER_DEFAULTS={'character':'','class':'Unknown','spec':'Succession','active':True,'exception':False,'group':'Unassigned'}
SPECIALIZATIONS=['Succession','Awakening','Ascension']

def optional_text(value,field,maximum):
    if not isinstance(value,str) or len(value)>maximum: raise Invalid(f'{field} must be text containing at most {maximum} characters')
    return value.strip()

def member_fields(data):
    """Validate and normalize the editable fields stored on a member record."""
    result=dict(data)
    result['name']=text(result.get('name'),'family name',80)
    for field,maximum in MEMBER_TEXT_FIELDS.items():
        result[field]=optional_text(result.get(field,MEMBER_DEFAULTS[field]),field,maximum)
    result['spec']=choice(result.get('spec',MEMBER_DEFAULTS['spec']),SPECIALIZATIONS,'specialization')
    for field in ('active','exception'):
        value=result.get(field,MEMBER_DEFAULTS[field])
        if not isinstance(value,bool): raise Invalid(f'{field} must be a boolean')
        result[field]=value
    result['joined']=date(result.get('joined',now()[:10]))
    return result

def member_errors(data):
    try: member_fields(data)
    except Invalid as exc: return str(exc)
    return ''

def handle(g,action,p,role,user):
    if action=='class':
        m=owner_or_self(g,role,user,p['member']); m.data['class']=text(p['class'],'class',40)
        m.data['spec']=choice(p.get('spec','Succession'),SPECIALIZATIONS,'specialization')
        backfill=p.get('backfill',False)
        if not isinstance(backfill,bool): raise Invalid('backfill must be a boolean')
        m.save()
        if backfill:
            require(role)
            for w in rows(g,'war'):
                for row in w.data['participants']:
                    if row['member']==m.key: row.update({'class':m.data['class'],'spec':m.data['spec']})
                w.save()
        return public(m)
    require(role)
    if action=='save':
        key=p.get('id'); old=get(g,'member',key).data if key else {}
        name=text(p.get('name',old.get('name')),'family name',80)
        if any(m.key!=key and m.data['name'].casefold()==name.casefold() for m in rows(g,'member')): raise Invalid('Family name already exists')
        data=member_fields({**old,'name':name,'character':p.get('character',old.get('character','')),'class':p.get('class',old.get('class','Unknown')),'spec':p.get('spec',old.get('spec','Succession')),'joined':p.get('joined',old.get('joined',now()[:10])),'active':p.get('active',old.get('active',True)),'exception':p.get('exception',old.get('exception',False)),'group':p.get('group',old.get('group','Unassigned'))})
        return public(save(g,'member',data,key))
    if action=='link':
        m=get(g,'member',p['member']); uid=str(p.get('user_id',''))
        if uid and any(str(x.data.get('user_id'))==uid and x.key!=m.key for x in rows(g,'member')): raise Invalid('Account already linked')
        m.data.update(user_id=uid,discord_id=str(p.get('discord_id',''))); m.save(); return public(m)
    if action=='vacation':
        m=get(g,'member',p['member']); start=date(p['start']); end=date(p['end'])
        if end<start: raise Invalid('Vacation ends before it starts')
        m.data.setdefault('vacations',[]).append({'start':start,'end':end}); m.save(); return public(m)
    if action=='note':
        m=get(g,'member',p['member']); notes=m.data.setdefault('notes',[]); note={'text':text(p['text'],maximum=4000),'at':now(),'by':user.username}
        if 'index' in p: notes[integer(p['index'],'note index',0,len(notes)-1)]=note
        else: notes.append(note)
        m.save(); return public(m)
    if action=='group': return public(save(g,'group',{'name':text(p['name']),'color':p.get('color','#63d9c5')},p.get('id')))
    if action=='sync':
        names=p.get('names',[])
        if not isinstance(names,list) or not names: raise Invalid('Empty roster rejected; supply a reviewed list of family names')
        names={text(n,'family name',80).casefold():n.strip() for n in names}
        current={m.data['name'].casefold():m for m in rows(g,'member')}
        added=0
        for key,name in names.items():
            if key not in current: handle(g,'save',{'name':name},role,user); added+=1
        for key,m in current.items(): m.data['active']=key in names; m.save()
        save(g,'retention',{'at':now(),'members':len(names)})
        return {'added':added,'inactive':len(set(current)-set(names))}
    if action=='merge':
        source=get(g,'member',p['source']); target=get(g,'member',p['target'])
        if source.pk==target.pk: raise Invalid('Choose two different members')
        for w in rows(g,'war'):
            source_rows=[r for r in w.data['participants'] if r['member']==source.key]
            target_row=next((r for r in w.data['participants'] if r['member']==target.key),None)
            for r in source_rows:
                if target_row:
                    target_row['kills']+=r['kills']; target_row['deaths']+=r['deaths']; w.data['participants'].remove(r)
                else: r['member']=target.key
            w.save()
        for kind in ['gear','assignment']:
            for r in rows(g,kind):
                if r.data.get('member')==source.key: r.data['member']=target.key; r.save()
        for event in rows(g,'event'):
            signups=event.data.get('signups',[]); target_present=any(s['member']==target.key for s in signups)
            for signup in list(signups):
                if signup['member']==source.key:
                    if target_present: signups.remove(signup)
                    else: signup['member']=target.key; target_present=True
            from .events import reconcile
            reconcile(event.data); event.save()
        target.data.setdefault('notes',[]).extend(source.data.get('notes',[])); target.data.setdefault('aliases',[]).append(source.data['name']); target.save()
        source.data.update(active=False,merged_into=target.key); source.save(); return public(target)
    if action=='remove':
        m=get(g,'member',p['member']); m.data['active']=False; m.save(); return {'inactive':m.key}
    raise Invalid('Unknown roster action')
