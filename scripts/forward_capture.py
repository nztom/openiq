"""Forward retained JSONL to a paired endpoint; replay from disk after restart."""
import argparse
import sys
import time
from pathlib import Path
from urllib.parse import urlparse
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import httpx
from guilds.capture import JsonLineTail


def forward(path,endpoint,token,once=False):
    parsed=urlparse(endpoint)
    if parsed.scheme!='https' and not (parsed.scheme=='http' and parsed.hostname in ('localhost','127.0.0.1','::1')):
        raise ValueError('Capture credentials require HTTPS, except on loopback.')
    tail=JsonLineTail(path);pending=[];delay=1
    with httpx.Client(timeout=20,follow_redirects=False) as client:
        while True:
            if not pending:pending=tail.read()
            if pending:
                batch=pending[:1000]
                try:
                    response=client.post(endpoint,headers={'Authorization':'Bearer '+token},json={'events':batch})
                    if response.status_code in (400,401,403,404,413):
                        raise ValueError('Capture rejected; check pairing, session status and input format. Source file is retained.')
                    response.raise_for_status()
                    if response.json().get('ok') is not True:raise ValueError('Capture acknowledgement is invalid; source file is retained.')
                except httpx.HTTPError:
                    print('Capture disconnected; retrying retained batch.',file=sys.stderr)
                    time.sleep(delay);delay=min(30,delay*2);continue
                pending=pending[len(batch):];delay=1
                continue
            if once:return
            time.sleep(.5)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file');parser.add_argument('--endpoint',required=True)
    parser.add_argument('--token-file',required=True,type=Path);parser.add_argument('--once',action='store_true')
    options=parser.parse_args()
    try:forward(options.file,options.endpoint,options.token_file.read_text().strip(),options.once)
    except KeyboardInterrupt:pass
    except ValueError as exc:parser.exit(1,str(exc)+'\n')
