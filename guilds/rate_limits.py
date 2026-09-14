"""Database-backed request budgets shared across web workers and restarts."""
import time,ipaddress
from django.conf import settings
from django.db import transaction,DatabaseError
from django.http import JsonResponse
from django.utils.crypto import salted_hmac
from .models import RequestLimit


def consume(identity,group,limit):
    now=int(time.time());window=now//60
    key=salted_hmac('openiq.request-limit',f'{identity}:{group}:{window}',algorithm='sha256').hexdigest()
    with transaction.atomic():
        RequestLimit.objects.filter(expires__lte=now).delete()
        row,_=RequestLimit.objects.select_for_update().get_or_create(key=key,defaults={'expires':(window+1)*60})
        if row.count>=limit:
            return False,row.expires-now
        row.count+=1;row.save(update_fields=['count'])
    return True,(window+1)*60-now


class RequestBudgets:
    def __init__(self,get_response):self.get_response=get_response
    def __call__(self,request):
        path=request.path;group=None
        if path=='/admin/login/' and request.method=='POST':group='admin_login'
        elif path.startswith('/auth/discord/') or path=='/login/':group='oauth'
        elif path=='/recover/':group='recovery'
        elif request.method not in ('GET','HEAD','OPTIONS'):
            if path.startswith('/ocr/'):group='ocr'
            elif path.startswith(('/api/','/capture/')) or path=='/onboard/':group='mutation'
        if group and settings.REQUEST_LIMITS_ENABLED:
            ip=request.META.get('REMOTE_ADDR','unknown')
            if settings.TRUST_PROXY_HEADERS and request.META.get('HTTP_X_FORWARDED_FOR'):
                candidate=request.META['HTTP_X_FORWARDED_FOR'].split(',')[-1].strip()
                try:ip=str(ipaddress.ip_address(candidate))
                except ValueError:pass
            identity='user:'+str(request.user.pk) if request.user.is_authenticated and group!='admin_login' else 'ip:'+ip
            try:allowed,retry=consume(identity,group,settings.REQUEST_LIMITS[group])
            except DatabaseError:return JsonResponse({'error':'Request protection unavailable; retry shortly'},status=503)
            if not allowed:
                response=JsonResponse({'error':'Too many requests. Retry shortly.','retry_after':retry},status=429)
                response['Retry-After']=str(retry);return response
        return self.get_response(request)
