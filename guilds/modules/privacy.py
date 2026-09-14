"""Guild-scoped member export and removal with anonymous historical scores."""
import re
from .core import *
from guilds.models import Access,Audit,Outbox


def handle(g,action,p,role,user):
    member=owner_or_self(g,role,user,p['member']);uid=str(member.data.get('user_id',''))
    labels={str(member.data.get(key,'')) for key in ('name','character','discord_id','twitch')}
    labels.update(str(value) for value in member.data.get('aliases',[]));labels.discard('')
    if action=='export':
        related=[]
        for record in rows(g,'war'):
            scores=[row for row in record.data['participants'] if row['member']==member.key]
            if scores:related.append({'kind':'war','id':record.key,'date':record.data['date'],'participants':scores})
        for kind in ('gear','assignment','ticket','application','reminder'):
            for record in rows(g,kind):
                if record.data.get('member')==member.key or (uid and str(record.data.get('user',''))==uid):related.append({'kind':kind,**public(record)})
        if role=='member':
            related=[r for r in related if r['kind']!='assignment']
        data=public(member)
        if role=='member':data.pop('notes',None)
        return {'format':'openiq-member-v1','member':data,'records':related,'exported':now()}
    if action=='unlink':
        member.data.update(user_id='',discord_id='',twitch='');member.save();return {'unlinked':member.key}
    if action not in ('anonymize','delete'):raise Invalid('Unknown privacy action')
    if p.get('confirmation')!=member.data['name']:raise Invalid('Type the member name to confirm removal of identifying data')
    from django.contrib.auth.models import User
    account=User.objects.filter(pk=uid).first() if uid.isdecimal() else None
    if action=='delete' and account:
        membership=Access.objects.filter(guild=g,user=account).first()
        if membership and membership.role=='owner' and Access.objects.filter(guild=g,role='owner').count()==1:raise Invalid('Assign another owner before deleting this membership')
    if account:labels.add(account.username)
    replacement='Removed member '+member.key[:8]
    pattern=re.compile(r'(?<!\w)(?:'+'|'.join(re.escape(label) for label in sorted(labels,key=len,reverse=True))+r')(?!\w)',re.IGNORECASE) if labels else None
    def scrub(value):
        if isinstance(value,str):return pattern.sub(replacement,value) if pattern else value
        if isinstance(value,list):return [scrub(item) for item in value]
        if isinstance(value,dict):return {key:scrub(item) for key,item in value.items()}
        return value
    for record in Record.objects.filter(guild=g).exclude(pk=member.pk):
        own=record.data.get('member')==member.key or (uid and str(record.data.get('user',''))==uid) or (uid and record.kind=='minigame' and record.key==uid)
        if own and record.kind in ('gear','assignment','ticket','application','reminder','minigame','capture_token'):
            if record.kind in ('ticket','reminder'):
                prefix=f'{g.pk}:{record.kind}:{record.key}'
                messages=Outbox.objects.filter(guild=g,key__startswith=prefix)
                keys=[str(pk) for pk in messages.values_list('pk',flat=True)]
                Record.objects.filter(guild=g,kind__in=['delivery','delivery_pending','delivery_retry','message_components'],key__in=keys).delete();messages.delete()
            if record.kind=='ticket':Record.objects.filter(guild=g,kind__in=['ticket_channel','ticket_pending'],key=record.key).delete()
            record.delete();continue
        record.data=scrub(record.data);record.save()
    for audit in Audit.objects.filter(guild=g):
        if account and audit.actor==account.username:audit.actor=replacement
        audit.data=scrub(audit.data);audit.save()
    for item in Outbox.objects.filter(guild=g):item.text=scrub(item.text);item.save(update_fields=['text'])
    Outbox.objects.filter(guild=g,key=f'{g.pk}:welcome:{member.key}').delete()
    member.data={'name':replacement,'class':'Unknown','spec':'Succession','active':False,'joined':now()[:10],'anonymized':True}
    member.save()
    if action=='delete' and account:Access.objects.filter(guild=g,user=account).delete()
    return {'anonymized':member.key,'membership_removed':action=='delete','historical_scores':'retained anonymously'}
