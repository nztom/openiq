"""Run the offline release checks in disposable application storage."""
import argparse,json,os,secrets,shutil,socket,subprocess,sys,tempfile,time,urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compose',help='Standalone Compose executable; otherwise use docker compose')
    parser.add_argument('--output',type=Path,default=ROOT/'release-report.json')
    options=parser.parse_args();results=[]
    with tempfile.TemporaryDirectory(prefix='openiq-release-') as directory:
        temporary=Path(directory);data=temporary/'data';data.mkdir()
        environment={key:value for key,value in os.environ.items() if not key.startswith(('DATABASE_','DISCORD_','TWITCH_','OLLAMA_','RATE_LIMIT_'))}
        environment.update(OPENIQ_DATA_DIR=str(data),DATABASE_BACKEND='sqlite',DATABASE_PATH=str(data/'db.sqlite3'),DEBUG='1',HTTPS='0',TRUST_PROXY='0',ALLOW_LOCAL_LOGIN='0',SEED_DEMO='0',ENABLE_DISCORD_DELIVERY='0',REQUIRED_PROCESSES='',REQUEST_LIMITS_ENABLED='0',SECRET_KEY=secrets.token_urlsafe(48),DEMO_PASSWORD=secrets.token_urlsafe(24),OPENIQ_BROWSER_TEST='1',OPENIQ_BROWSER_ARTIFACTS=str(temporary/'screenshots'),ALLOWED_HOSTS='localhost,127.0.0.1,testserver',PYTHONIOENCODING='utf-8')
        def run(name,arguments,env=None,timeout=600):
            print('Checking '+name+'...',flush=True)
            try:
                completed=subprocess.run(arguments,cwd=ROOT,env=env or environment,text=True,encoding='utf-8',errors='replace',stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
                result={'check':name,'passed':completed.returncode==0,'exit_code':completed.returncode,'output':completed.stdout}
            except (OSError,subprocess.TimeoutExpired) as error:result={'check':name,'passed':False,'error':type(error).__name__}
            results.append(result)
            print(('PASS ' if result['passed'] else 'FAIL ')+name,flush=True)
            if not result['passed']:print(result.get('output',result.get('error',''))[-5000:],flush=True)
            return result['passed']
        python=sys.executable
        run('Django checks',[python,'manage.py','check'])
        secure={**environment,'DEBUG':'0','HTTPS':'1','ALLOW_LOCAL_LOGIN':'0','REQUEST_LIMITS_ENABLED':'1','HSTS_SECONDS':'31536000','HSTS_INCLUDE_SUBDOMAINS':'1','HSTS_PRELOAD':'1'}
        run('Django deployment checks',[python,'manage.py','check','--deploy','--fail-level','WARNING'],secure)
        run('Python and browser regressions',[python,'-m','coverage','run','manage.py','test','--noinput'])
        run('100% statement and branch coverage',[python,'-m','coverage','report'])
        run('Discord command registry',[python,'manage.py','runbot','--check'])
        run('CSV OCR IKUSA JSONL compatibility',[python,'manage.py','verify_imports'])
        run('Packet fixtures',[python,'scripts/verify_packets.py'])
        for source in sorted((ROOT/'static').glob('*.js')):run('JavaScript '+source.name,['node','--check',str(source)])
        compose=[options.compose] if options.compose else ['docker','compose']
        run('Compose configuration',[*compose,'--env-file','.env.example','--profile','jobs','--profile','discord','config','--quiet'])
        environment['ALLOW_LOCAL_LOGIN']='1'
        if run('Disposable database migration',[python,'manage.py','migrate','--noinput']) and run('Disposable browser fixtures',[python,'manage.py','seed_demo']):
            with socket.socket() as port_socket:port_socket.bind(('127.0.0.1',0));port=port_socket.getsockname()[1]
            environment['OPENIQ_URL']=f'http://127.0.0.1:{port}'
            with (temporary/'server.log').open('w',encoding='utf-8') as log:
                server=subprocess.Popen([python,'manage.py','runserver',f'127.0.0.1:{port}','--noreload'],cwd=ROOT,env=environment,stdout=log,stderr=subprocess.STDOUT)
                try:
                    ready=False
                    for attempt in range(100):
                        if server.poll() is not None:break
                        try:
                            with urllib.request.urlopen(environment['OPENIQ_URL']+'/healthz/',timeout=1):ready=True;break
                        except OSError:time.sleep(.1)
                    if ready:run('Complete browser war lifecycle',[python,'scripts/browser_smoke.py'])
                    else:results.append({'check':'Browser server startup','passed':False})
                finally:
                    server.terminate()
                    try:server.wait(timeout=15)
                    except subprocess.TimeoutExpired:server.kill();server.wait(timeout=5)
        report={'passed':all(result['passed'] for result in results),'checks':results,'scope':'Offline synthetic fixtures and controlled remote responses; live launch checks are separate.'}
        options.output.parent.mkdir(parents=True,exist_ok=True)
        options.output.write_text(json.dumps(report,indent=2),encoding='utf-8')
        print('Release report: '+str(options.output.resolve()),flush=True)
        return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
