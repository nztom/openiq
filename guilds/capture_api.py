"""Session-scoped bearer capture with durable server acknowledgement."""
import hashlib
import json
import secrets
import time
from django.http import JsonResponse
from django.db import transaction
from django.db.models import F
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils.crypto import constant_time_compare
from django.contrib.auth.models import User
from .models import Guild,Record
from .services import execute,access
from .modules.core import get,save,require,Invalid,now
from django.core.exceptions import PermissionDenied


def pair(user,guild,session):
    require(access(user,guild));record=get(guild,'session',session)
    if not guild.config.get('capture',{}).get('enabled',True):
        raise Invalid('Capture is disabled in guild settings')
    if record.data['status']!='live':
        raise Invalid('Session is stopped')
    token=secrets.token_urlsafe(32)
    save(guild,'capture_token',{'digest':hashlib.sha256(token.encode()).hexdigest(),'user':user.pk,'expires':time.time()+3600*guild.config.get('capture',{}).get('token_hours',24)},session)
    return token


@csrf_exempt
@require_POST
def ingest(request,guild_id,session):
    header=request.headers.get('Authorization','')
    if not header.startswith('Bearer ') or len(header)>200:
        return JsonResponse({'error':'Invalid capture credential'},status=401)
    token=header[7:]
    with transaction.atomic():
        Guild.objects.filter(pk=guild_id).update(revision=F('revision')+1)
        credential=Record.objects.filter(guild_id=guild_id,kind='capture_token',key=session).first()
        if not credential or credential.data['expires']<=time.time() or not constant_time_compare(credential.data['digest'],hashlib.sha256(token.encode()).hexdigest()):
            return JsonResponse({'error':'Invalid or expired capture credential'},status=401)
        try:
            if not credential.guild.config.get('capture',{}).get('enabled',True):
                raise PermissionDenied()
            if len(request.body)>1024*1024:
                return JsonResponse({'error':'Capture batch exceeds 1 MiB'},status=413)
            payload=json.loads(request.body)
            user=User.objects.get(pk=credential.data['user'])
            if not user.is_active:
                raise PermissionDenied()
            result=execute(user,guild_id,'live','ingest',{'session':session,'events':payload['events']})
            record=get(credential.guild,'session',session)
            record.data['capture_last_seen']=now()
            diagnostics=record.data.setdefault('capture_diagnostics',[])
            diagnostics.append({'at':record.data['capture_last_seen'],'added':result['added'],'received':len(payload['events'])})
            record.data['capture_diagnostics']=diagnostics[-credential.guild.config.get('capture',{}).get('diagnostic_entries',50):];record.save()
            return JsonResponse({'ok':True,**result})
        except (Invalid,KeyError,TypeError,ValueError):return JsonResponse({'error':'Invalid capture batch or stopped session'},status=400)
        except (PermissionDenied,User.DoesNotExist):return JsonResponse({'error':'Capture access revoked'},status=403)
