"""Discord authorization-code flow with server-side tokens and refreshed roles."""
import os,secrets,time
from urllib.parse import urlencode
import httpx
from django.conf import settings
from django.contrib.auth import login,logout
from django.contrib.auth.views import LoginView
from django.contrib.auth.models import User
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect,render
from django.db import transaction
from django.views.decorators.http import require_POST
from guilds.models import Guild,Access

API='https://discord.com/api/v10'
MANAGE_GUILD=0x20
ADMINISTRATOR=0x8

def login_entry(request):
    if settings.ALLOW_LOCAL_LOGIN:return LoginView.as_view()(request)
    return render(request,'registration/discord_login.html')

@require_POST
def logout_entry(request):
    logout(request)
    return redirect('/login/')

def credentials():return os.getenv('DISCORD_CLIENT_ID'),os.getenv('DISCORD_CLIENT_SECRET'),os.getenv('DISCORD_REDIRECT_URI','http://127.0.0.1:8765/auth/discord/callback/')
def begin(request):
    client,secret,uri=credentials()
    if not client or not secret:return HttpResponseBadRequest('Discord login is not configured. Ask the OpenIQ operator to configure it.')
    state=secrets.token_urlsafe(32);request.session['oauth_state']={'value':state,'at':time.time()}
    return redirect('https://discord.com/oauth2/authorize?'+urlencode({'client_id':client,'redirect_uri':uri,'response_type':'code','scope':'identify guilds guilds.members.read','state':state}))

def role_for(g,server,roles):
    configured=g.config.get('roles',{})
    if server.get('owner'):return 'owner'
    for tier in ['owner','admin','member']:
        allowed=configured.get(tier,[])
        if isinstance(allowed,str):allowed=[allowed]
        if set(map(str,allowed))&set(map(str,roles)):return tier
    if not configured and int(server.get('permissions','0'))&8:return 'owner'
    return None

def can_manage_server(server):
    try:return bool(server.get('owner')) or bool(int(server.get('permissions','0'))&(ADMINISTRATOR|MANAGE_GUILD))
    except (TypeError,ValueError):return False

def session_servers(servers):
    return [{'id':str(server['id']),'name':str(server.get('name',''))[:100],'owner':bool(server.get('owner')),'permissions':str(server.get('permissions','0'))} for server in servers if str(server.get('id','')).isdecimal()]

def synchronize(user,token):
    headers={'Authorization':'Bearer '+token}
    with httpx.Client(timeout=15) as client:
        response=client.get(API+'/users/@me/guilds',headers=headers);response.raise_for_status();servers={str(s['id']):s for s in response.json()}
        changes=[]
        for g in Guild.objects.exclude(server_id=''):
            server=servers.get(g.server_id);tier=None
            if server:
                response=client.get(API+f'/users/@me/guilds/{g.server_id}/member',headers=headers)
                if response.status_code not in [403,404]:response.raise_for_status()
                if response.status_code==200:tier=role_for(g,server,response.json().get('roles',[]))
            changes.append((g,tier))
    with transaction.atomic():
        for g,tier in changes:
            if tier:Access.objects.update_or_create(user=user,guild=g,defaults={'role':tier})
            else:Access.objects.filter(user=user,guild=g).delete()
    return session_servers(servers.values())

def callback(request):
    expected=request.session.pop('oauth_state',{})
    supplied=request.GET.get('state','')
    try:valid=bool(expected) and time.time()-float(expected.get('at',0))<=600 and isinstance(expected.get('value'),str) and isinstance(supplied,str) and secrets.compare_digest(expected['value'],supplied)
    except (TypeError,ValueError):valid=False
    if not valid:return HttpResponseBadRequest('Invalid or expired login state')
    if request.GET.get('error'):return HttpResponseBadRequest('Discord authorization was denied. Start sign-in again when ready.')
    client,secret,uri=credentials()
    try:
        response=httpx.post(API+'/oauth2/token',data={'client_id':client,'client_secret':secret,'grant_type':'authorization_code','code':request.GET.get('code',''),'redirect_uri':uri},timeout=15);response.raise_for_status();tokens=response.json()
        response=httpx.get(API+'/users/@me',headers={'Authorization':'Bearer '+tokens['access_token']},timeout=15);response.raise_for_status();profile=response.json()
        user,created=User.objects.get_or_create(username='discord_'+profile['id'])
        if created or user.has_usable_password():user.set_unusable_password();user.save()
        servers=synchronize(user,tokens['access_token']);login(request,user)
        request.session['discord_tokens']={'access':tokens['access_token'],'refresh':tokens.get('refresh_token'),'expires':time.time()+tokens['expires_in']};request.session['discord_checked']=time.time()
        request.session['discord_guilds']=servers
        return redirect('/')
    except (httpx.HTTPError,KeyError,TypeError,ValueError):return HttpResponseBadRequest('Discord login could not be completed. Retry or contact the OpenIQ operator.')

class RefreshDiscordRoles:
    def __init__(self,get_response):self.get_response=get_response
    def __call__(self,request):
        tokens=request.session.get('discord_tokens')
        if request.user.is_authenticated and tokens and time.time()-request.session.get('discord_checked',0)>180:
            try:
                if tokens['expires']<time.time()+60:
                    refresh=tokens.get('refresh')
                    if not refresh:raise KeyError('refresh')
                    client,secret,_=credentials();response=httpx.post(API+'/oauth2/token',data={'client_id':client,'client_secret':secret,'grant_type':'refresh_token','refresh_token':refresh},timeout=15);response.raise_for_status();data=response.json();tokens={'access':data['access_token'],'refresh':data.get('refresh_token',refresh),'expires':time.time()+data['expires_in']};request.session['discord_tokens']=tokens
                request.session['discord_guilds']=synchronize(request.user,tokens['access']);request.session['discord_checked']=time.time()
            except (httpx.HTTPError,KeyError,TypeError,ValueError):
                # Fail closed when current Discord privileges cannot be verified.
                logout(request);return redirect('/login/')
        return self.get_response(request)
