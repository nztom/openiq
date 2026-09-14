"""Readiness facts and private local process heartbeats."""
import json,os,tempfile,time
from pathlib import Path
from django.conf import settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


def heartbeat(process,ready=True,max_age=120):
    destination=settings.DATA_DIR/('.heartbeat-'+process+'.json')
    with tempfile.NamedTemporaryFile(mode='w',dir=settings.DATA_DIR,delete=False,encoding='utf-8') as stream:
        temporary=Path(stream.name);json.dump({'at':time.time(),'ready':ready,'max_age':max_age},stream)
    try:temporary.chmod(0o600);os.replace(temporary,destination)
    finally:temporary.unlink(missing_ok=True)


def readiness():
    checks={}
    try:
        with connection.cursor() as cursor:cursor.execute('SELECT 1');cursor.fetchone()
        checks['database']=True
        executor=MigrationExecutor(connection)
        checks['migrations']=not bool(executor.migration_plan(executor.loader.graph.leaf_nodes()))
    except Exception:checks.update(database=False,migrations=False)
    try:
        with tempfile.TemporaryFile(dir=settings.DATA_DIR) as stream:stream.write(b'ready');stream.flush()
        checks['storage']=True
    except OSError:checks['storage']=False
    for process in settings.REQUIRED_PROCESSES:
        try:
            data=json.loads((settings.DATA_DIR/('.heartbeat-'+process+'.json')).read_text())
            checks[process]=bool(data['ready'] and 0<=time.time()-data['at']<120)
        except (OSError,ValueError,KeyError,TypeError):checks[process]=False
    return {'status':'ok' if all(checks.values()) else 'unavailable','version':settings.OPENIQ_VERSION,'checks':checks}
