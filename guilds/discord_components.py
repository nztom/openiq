"""Discord component payloads and authorization share the local event services."""
from .modules.core import Invalid,own_member
from .models import Guild,Record
from .services import execute,access
from django.db import transaction
from django.utils.crypto import salted_hmac,constant_time_compare
from .modules.core import save

def signed_id(kind,g,key,index,layout=''):
    value=f'{kind}:{g.pk}:{key}:{index}'
    signature=salted_hmac('openiq.discord.component',value+'|'+layout,algorithm='sha256').hexdigest()[:16]
    return value+':'+signature

def event_components(g,event):
    # Discord allows at most 5 action rows with at most 5 buttons each.
    import json
    layout=json.dumps([t['name'] for t in event.data['teams']])
    disabled=bool(event.data.get('locked') or event.data.get('archived'))
    buttons=[{'type':2,'style':1,'label':team['name'][:80],'disabled':disabled,'custom_id':signed_id('signup',g,event.key,i,layout)} for i,team in enumerate(event.data['teams'][:24])]
    buttons.append({'type':2,'style':2,'label':'Withdraw','disabled':disabled,'custom_id':signed_id('signup',g,event.key,'withdraw',layout)})
    return [{'type':1,'components':buttons[i:i+5]} for i in range(0,len(buttons),5)]

def process(user,custom_id,deliver_roles=False,interaction_id=None):
    if deliver_roles and custom_id.startswith('welcome:'):
        prepared=_process(user,custom_id,deliver_roles,interaction_id,prepare_only=True)
        if prepared.get('duplicate'):
            return prepared
        from .discord_welcome import choose
        result=choose(user,prepared['guild'],prepared['member'],prepared['role'],enabled=True)
        return _process(user,custom_id,deliver_roles,interaction_id,welcome_result=result)
    return _process(user,custom_id,deliver_roles,interaction_id)


@transaction.atomic
def _process(user,custom_id,deliver_roles=False,interaction_id=None,prepare_only=False,welcome_result=None):
    fields=custom_id.split(':')
    if len(fields) not in [4,5] or fields[0] not in ['signup','welcome'] or not fields[1].isdecimal():raise Invalid('Unknown component')
    kind,gid,key,index=fields[:4];g=Guild.objects.get(pk=gid);access(user,g)
    from django.db.models import F
    Guild.objects.filter(pk=g.pk).update(revision=F('revision')+1)
    layout=''
    if kind=='signup':
        import json
        event=Record.objects.get(guild=g,kind='event',key=key)
        layout=json.dumps([t['name'] for t in event.data['teams']])
    if deliver_roles or len(fields)==5:
        if not constant_time_compare(custom_id,signed_id(kind,g,key,index,layout)):raise Invalid('This card is outdated or invalid. Ask an officer to publish it again.')
    if interaction_id:
        previous=Record.objects.filter(guild=g,kind='bot_receipt',key=str(interaction_id)).first()
        if previous:
            if previous.data!={'user':user.pk,'component':custom_id}:raise Invalid('Interaction already used')
            return {'duplicate':True}
    if kind=='welcome':
        if prepare_only:
            return {'guild':g,'member':key,'role':index}
        if welcome_result is not None:
            result=welcome_result
        else:
            from .discord_welcome import choose
            result=choose(user,g,key,index,enabled=False)
    else:
        member=own_member(g,user)
        if not member:raise Invalid('Ask an officer to link your account first')
        try:
            if index!='withdraw' and (not index.isdecimal() or int(index)>=len(event.data['teams'])):raise ValueError()
            team='' if index=='withdraw' else event.data['teams'][int(index)]['name']
        except (ValueError,IndexError):raise Invalid('Team no longer exists')
        result=execute(user,g.pk,'events','signup',{'event':key,'member':member.key,'team':team})
    if interaction_id:save(g,'bot_receipt',{'user':user.pk,'component':custom_id},str(interaction_id))
    return result
