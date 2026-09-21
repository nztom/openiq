import uuid
from datetime import datetime, timezone
from django.core.exceptions import PermissionDenied
from guilds.models import Record

class Invalid(ValueError): pass

def now(): return datetime.now(timezone.utc).isoformat()
def ident(): return str(uuid.uuid4())
def text(value, field='text', maximum=300):
    if not isinstance(value,str) or not value.strip() or len(value)>maximum: raise Invalid(f'{field} must contain 1–{maximum} characters')
    return value.strip()
def number(value, field, minimum=0, maximum=10000000):
    if isinstance(value,bool): raise Invalid(f'{field} must be a number')
    try: n=float(value)
    except (ValueError,TypeError): raise Invalid(f'{field} must be a number')
    if not minimum <= n <= maximum: raise Invalid(f'{field} must be between {minimum} and {maximum}')
    return n
def integer(value, field, minimum=0, maximum=10000000):
    n=number(value,field,minimum,maximum)
    if n != int(n): raise Invalid(f'{field} must be a whole number')
    return int(n)
def choice(value, allowed, field):
    if value not in allowed: raise Invalid(f'{field} must be one of {", ".join(allowed)}')
    return value
def date(value):
    try: return datetime.fromisoformat(value).date().isoformat()
    except (ValueError,TypeError): raise Invalid('Use an ISO date (YYYY-MM-DD)')
def timestamp(value):
    try:
        d=datetime.fromisoformat(value.replace('Z','+00:00'))
        if d.tzinfo is None: raise ValueError()
        return d.astimezone(timezone.utc).isoformat()
    except (ValueError,TypeError,AttributeError): raise Invalid('Date/time must include a timezone offset')
def require(role, level='admin'):
    if {'member':0,'admin':1,'owner':2}.get(role,-1)<{'member':0,'admin':1,'owner':2}[level]: raise PermissionDenied('This action requires '+level+' access')
def rows(g,kind): return list(Record.objects.filter(guild=g,kind=kind).order_by('created'))
def get(g,kind,key):
    try: return Record.objects.get(guild=g,kind=kind,key=str(key))
    except Record.DoesNotExist: raise Invalid(f'{kind} not found')
def save(g,kind,data,key=None):
    key=str(key or ident())
    obj,_=Record.objects.update_or_create(guild=g,kind=kind,key=key,defaults={'data':data})
    return obj

def public(obj):
    result={'id':obj.key,**obj.data}
    if obj.kind=='challenge' and result.get('status')=='pending':result.pop('roll',None)
    return result
def kdr(k,d): return round(k/d,3) if d else (None if k else 0)
def own_member(g,user):
    return next((r for r in rows(g,'member') if str(r.data.get('user_id'))==str(user.pk)),None)
def owner_or_self(g,role,user,member_id):
    m=get(g,'member',member_id)
    if role=='member' and str(m.data.get('user_id'))!=str(user.pk): raise PermissionDenied('You may only change your linked member')
    return m
