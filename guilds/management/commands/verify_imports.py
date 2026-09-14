"""Report compatibility of checked-in synthetic import formats without writing data."""
import csv,json
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand,CommandError
from guilds.capture import JsonLineTail
from guilds.modules.integrations import ocr,paired_scores
from guilds.modules.logformat import parse_log


class Command(BaseCommand):
    help='Validate synthetic CSV, OCR, IKUSA and JSONL fixtures and emit an operator report.'
    def add_arguments(self,parser):
        parser.add_argument('--fixtures',type=Path,default=settings.BASE_DIR/'fixtures')
        parser.add_argument('--output',type=Path)

    def handle(self,*args,**options):
        root=options['fixtures'];checks=[]
        def check(name,callback):
            try:
                if not callback():raise ValueError('Unexpected fixture result')
                checks.append({'format':name,'status':'pass'})
            except Exception as exc:
                checks.append({'format':name,'status':'fail','reason':type(exc).__name__+'; check fixture files and required import dependencies'})
        def csv_check():
            with (root/'scores.csv').open(newline='',encoding='utf-8-sig') as source:rows=list(csv.DictReader(source))
            return rows==[{'name':'Aster','kills':'42','deaths':'7'},{'name':'Juniper','kills':'14','deaths':'5'}]
        def ocr_check():
            return paired_scores([ocr((root/'ocr'/name).read_bytes()) for name in ('war-names.png','war-scores.png')])==[{'name':'TestAlpha','kills':11,'deaths':2},{'name':'TestBeta','kills':7,'deaths':3}]
        def ikusa_check():
            events=parse_log((root/'ikusa.log').read_text(),'2026-09-11')
            return len(events)==2 and events[0]['kind']=='kill' and events[1]['target']=='Aster' and events[1]['at'].startswith('2026-09-12')
        def jsonl_check():
            tail=JsonLineTail(root/'combat.jsonl');events=tail.read()
            return len(events)==2 and events[0]['id']=='fixture-1' and events[1]['kind']=='death' and tail.read()==[]
        for name,callback in [('CSV',csv_check),('OCR',ocr_check),('IKUSA',ikusa_check),('JSONL',jsonl_check)]:check(name,callback)
        report=json.dumps({'synthetic_only':True,'checks':checks,'passed':all(c['status']=='pass' for c in checks)},indent=2)
        if options['output']:options['output'].write_text(report+'\n',encoding='utf-8')
        self.stdout.write(report)
        if any(c['status']=='fail' for c in checks):raise CommandError('Import compatibility checks failed; see the report above.')
