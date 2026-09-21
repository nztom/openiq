import json
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404,redirect
from django.views.decorators.http import require_POST,require_http_methods
from django.core.exceptions import PermissionDenied
from .models import Guild,Record,Access,Audit,Outbox
from .services import access,execute
from .modules.core import public,Invalid
from .modules import analytics,alliances,coaching,gear,live,integrations,intelligence
from .catalog import ACTIONS

@login_required
def index(request):
    guilds=Guild.objects.filter(access__user=request.user).order_by('name')
    if not guilds.exists():
        return redirect('/onboard/')
    return render(request,'dashboard.html',{'guilds':guilds,'actions':ACTIONS})

@login_required
def state(request,guild_id):
    g=get_object_or_404(Guild,pk=guild_id); role=access(request.user,g)
    records={}
    private={'lead','assignment','adoption','import','war_revision','delivery','delivery_retry','delivery_pending','ticket_channel','ticket_pending','welcome_delivery'}
    for r in Record.objects.filter(guild=g).exclude(kind__in=['alliance','adoption','bot_receipt','capture_token']):
        if role=='member' and r.kind in private: continue
        if r.kind in ['ticket','application','reminder','minigame'] and role=='member' and r.data.get('user',r.key)!=request.user.pk and str(r.data.get('user',r.key))!=str(request.user.pk): continue
        d=public(r)
        if r.kind=='member' and role=='member': d.pop('notes',None)
        if r.kind=='challenge' and d.get('status')=='pending':d.pop('roll',None)
        if r.kind=='session': d['summary']=live.summarize(r)
        records.setdefault(r.kind,[]).append(d)
    records['alliance']=alliances.overview(g)
    from .war_checklist import checklist
    result={'guild':{'id':g.pk,'name':g.name,'revision':g.revision,'config':g.config if role=='owner' else {}},'role':role,'user':{'id':request.user.pk,'name':request.user.username},'records':records,'analytics':analytics.calculate(g,request.GET),'intelligence':intelligence.extended(g),'rankings':gear.rankings(g),'gear':gear.current(g),'flags':coaching.flags(g) if role!='member' else [],'actions':[a for a in ACTIONS if {'member':0,'admin':1,'owner':2}[a['role']]<={'member':0,'admin':1,'owner':2}[role]],'guilds':list(Guild.objects.filter(access__user=request.user).distinct().values('id','name')),'accounts':list(Access.objects.filter(guild=g).values('user_id','user__username','role')) if role=='owner' else []}
    if role!='member': result.update(outbox=list(Outbox.objects.filter(guild=g).order_by('-created').values('id','text','status','created')[:100]),audit=list(Audit.objects.filter(guild=g).order_by('-created').values('actor','action','created')[:100]))
    if role!='member':result['war_checklist']=checklist(g)
    if role=='owner':
        from .integration_status import status
        from .modules.commands import COMMANDS
        result['integration_status']=status(g);result['command_names']=COMMANDS
    return JsonResponse(result)

@login_required
@require_POST
def action(request,guild_id,module,name):
    try:
        payload=json.loads(request.body)
        return JsonResponse({'ok':True,'result':execute(request.user,guild_id,module,name,payload)})
    except (Invalid,KeyError,TypeError,json.JSONDecodeError) as e: return JsonResponse({'ok':False,'error':str(e)},status=400)
    except PermissionDenied as e: return JsonResponse({'ok':False,'error':str(e)},status=403)

@login_required
@require_POST
def ocr_view(request,guild_id):
    role=access(request.user,guild_id)
    if role=='member' and request.POST.get('mode')!='gear':
        raise PermissionDenied()
    try:
        files=request.FILES.getlist('images')
        if getattr(request,'upload_too_large',False) or sum(f.size for f in files)>12*1024*1024:
            return JsonResponse({'error':'Combined images exceed 12 MiB'},status=413)
        if not files or len(files)>10:
            raise Invalid('Choose 1–10 images')
        import time
        deadline=time.monotonic()+45;texts=[]
        for file in files:
            remaining=deadline-time.monotonic()
            if remaining<=0:
                raise Invalid('OCR request exceeded its processing budget')
            texts.append(integrations.ocr(file.read(),timeout=remaining))
        result={'texts':texts,'review_required':True}
        if request.POST.get('mode')=='gear':result['gear']=integrations.gear_numbers(texts)
        else:
            try:result['draft']=execute(request.user,guild_id,'wars','review',{'rows':integrations.paired_scores(texts)})
            except Invalid as exc:result['review_error']=str(exc)
        return JsonResponse(result)
    except (Invalid,ValueError) as e: return JsonResponse({'error':str(e)},status=400)

def recap(request,token):
    session=next((r for r in Record.objects.filter(kind='session') if r.data.get('public') and r.data.get('share_token')==str(token)),None)
    if not session:
        from django.http import Http404
        raise Http404()
    return render(request,'recap.html',{'session':session.data,'summary':live.summarize(session)})

@login_required
@require_http_methods(['GET','POST'])
def onboard(request):
    from django.db import transaction
    from .modules.core import text,choice
    regions=['NA','EU','SEA','KR','JP','TW','SA','RU','MENA']
    if request.method=='GET':
        import os
        from .discord_auth import can_manage_server
        servers=[server for server in request.session.get('discord_guilds',[]) if can_manage_server(server)]
        return render(request,'onboard.html',{'servers':servers,'regions':regions,'development':settings.ALLOW_LOCAL_LOGIN,'client_id':os.getenv('DISCORD_CLIENT_ID','')})
    try:
        p=json.loads(request.body)
        if not isinstance(p,dict):raise Invalid('Onboarding payload must be a JSON object')
        server_id=str(p.get('server_id',''))
        if not settings.ALLOW_LOCAL_LOGIN:
            from .discord_auth import can_manage_server
            if not request.session.get('discord_tokens') or not request.user.username.startswith('discord_'):
                raise PermissionDenied('Discord login is required to create a guild')
            server=next((server for server in request.session.get('discord_guilds',[]) if server.get('id')==server_id),None)
            if not server or not can_manage_server(server):
                raise PermissionDenied('Discord owner, Administrator, or Manage Guild permission is required')
        with transaction.atomic():
            name=text(p['name'],'guild name',80)
            if Guild.objects.filter(name__iexact=name).exists():
                raise Invalid('That guild already exists')
            g=Guild.objects.create(name=name,region=choice(p.get('region','NA'),regions,'region'),server_id=server_id)
            Access.objects.create(guild=g,user=request.user,role='owner')
            if p.get('names'):execute(request.user,g.pk,'roster','sync',{'names':p['names']})
        return JsonResponse({'id':g.pk,'name':g.name})
    except (Invalid,KeyError,TypeError,ValueError) as e:return JsonResponse({'error':str(e)},status=400)

@login_required
def ally_event(request,token):
    from .modules.alliances import visible
    from django.http import Http404
    e=next((r for r in Record.objects.filter(kind='event') if r.data.get('alliance_share') and r.data.get('share_token')==str(token)),None)
    if not e:
        raise Http404()
    accessible=set(Guild.objects.filter(access__user=request.user).values_list('id',flat=True))
    if e.guild_id not in accessible and not any(a.data['status']=='active' and accessible.intersection(map(int,a.data['guilds'])) for a in visible(e.guild)):
        raise PermissionDenied()
    from .modules.core import rows
    names={m.key:m.data['name'] for m in rows(e.guild,'member')}
    return render(request,'ally_event.html',{'event':e.data,'guild':e.guild.name,'signups':[{**s,'name':names.get(s['member'],'Unknown')} for s in e.data['signups']]})


@login_required
@require_POST
def recover(request):
    import secrets,hashlib
    from django.db import transaction
    from .modules.core import now,text
    try:
        p=json.loads(request.body)
        server_id=text(p['server_id'],'Discord server ID',30)
        if not settings.ALLOW_LOCAL_LOGIN:
            from .discord_auth import can_manage_server,synchronize
            tokens=request.session.get('discord_tokens')
            if not tokens or not request.user.username.startswith('discord_'):
                raise PermissionDenied('Discord login is required for guild recovery')
            import httpx
            try:servers=synchronize(request.user,tokens['access'])
            except (httpx.HTTPError,KeyError,ValueError,TypeError):raise PermissionDenied('Discord authority could not be verified')
            request.session['discord_guilds']=servers
            if not any(server['id']==server_id and can_manage_server(server) for server in servers):
                raise PermissionDenied('Manage Guild permission is required on the destination Discord server')
        with transaction.atomic():
            g=get_object_or_404(Guild,pk=p['guild'])
            from django.db.models import F
            Guild.objects.filter(pk=g.pk).update(revision=F('revision')+1)
            key=Record.objects.filter(guild=g,kind='adoption',key='current').first()
            digest=hashlib.sha256(str(p['key']).encode()).hexdigest()
            if not key or key.data['used'] or key.data.get('expires','')<now() or not secrets.compare_digest(key.data.get('token_hash',''),digest):
                raise Invalid('Invalid or expired adoption key')
            previous_server=g.server_id
            g.server_id=server_id;g.save()
            key.data.update(used=True,redeemed_by=request.user.username);key.save()
            Access.objects.update_or_create(guild=g,user=request.user,defaults={'role':'owner'})
            Audit.objects.create(guild=g,actor=request.user.username,action='admin.recover',data={'issued_by':key.data.get('issued_by','unknown'),'redeemed_by':request.user.username,'previous_server':previous_server,'server_id':server_id})
        return JsonResponse({'id':g.pk})
    except (Invalid,KeyError,ValueError,TypeError) as e:return JsonResponse({'error':str(e)},status=400)


def health(request):
    return JsonResponse({'status':'ok','application':'OpenIQ'})


def ready(request):
    from .health import readiness
    report=readiness()
    return JsonResponse(report,status=200 if report['status']=='ok' else 503)
