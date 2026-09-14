from django.db import transaction
from django.db.models import F
from guilds.models import Guild, Access, Audit
from .modules.core import Invalid
from .modules.registry import MODULES
from django.core.exceptions import PermissionDenied

def access(user,guild):
    if not user.is_authenticated: raise PermissionDenied('Sign in first')
    try: return Access.objects.get(user=user,guild=guild).role
    except Access.DoesNotExist: raise PermissionDenied('You do not have access to this guild')


def response_for_role(value,role):
    """Never return officer-only notes through a successful member action."""
    if role!='member':return value
    if isinstance(value,dict):return {key:response_for_role(item,role) for key,item in value.items() if key!='notes'}
    if isinstance(value,list):return [response_for_role(item,role) for item in value]
    return value

def execute(user,guild_id,module,action,payload):
    from .remote_actions import prepare
    role=access(user,guild_id)
    snapshot=Guild.objects.get(pk=guild_id)
    authorize(snapshot,module,action,payload,role)
    prepared=prepare(snapshot,module,action,payload,role,user)
    return commit(user,guild_id,module,action,payload,snapshot,prepared,role)


def authorize(g,module,action,payload,role):
    if module not in MODULES: raise Invalid('Unknown module')
    if not isinstance(payload,dict): raise Invalid('Payload must be an object')
    from .catalog import ACTIONS
    from .modules.core import require
    declared=next((item for item in ACTIONS if item['module']==module and item['action']==action),None)
    if declared:require(role,declared['role'])
    from .remote_actions import authorize as command_authority
    command_authority(g,module,action,payload,role)


@transaction.atomic
def commit(user,guild_id,module,action,payload,snapshot,prepared,prepared_role):
    # ORM UPDATE serializes mutations: SQLite takes its writer lock; PostgreSQL
    # locks the guild row until this transaction ends. Read records afterward.
    Guild.objects.filter(pk=guild_id).update(revision=F('revision')+1)
    g=Guild.objects.get(pk=guild_id)
    role=access(user,guild_id)
    authorize(g,module,action,payload,role)
    if prepared is not None and (role!=prepared_role or g.revision!=snapshot.revision+1 or g.config!=snapshot.config):
        raise Invalid('Guild changed while external data was loading; retry the action')
    from .war_history import recording
    with recording(user,module,action):
        result=prepared(g,role) if prepared is not None else MODULES[module].handle(g,action,payload,role,user)
    if module in ['events','commands'] and isinstance(result,dict) and result.get('id'):
        from guilds.models import Outbox,Record
        event=Record.objects.filter(guild=g,kind='event',key=str(result['id'])).first()
        if event and Outbox.objects.filter(guild=g,key=f'{g.pk}:event:{event.key}').exists():
            MODULES['community'].handle(g,'post_event',{'event':event.key},'admin',user)
    if g.pk: Audit.objects.create(guild=g,actor='privacy-request' if module=='privacy' and action in ('anonymize','delete') else user.username,action=module+'.'+action,data={'result_id':result.get('id')} if isinstance(result,dict) else {})
    return response_for_role(result,role)
