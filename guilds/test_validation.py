"""Boundary validation and failure recovery contracts."""
import json,tempfile,zipfile,hashlib,os
from pathlib import Path
from unittest.mock import patch
from django.test import SimpleTestCase
from .modules.core import Invalid,text,number,integer,date,timestamp
from .modules.logformat import parse_log
from .updater import install_release,version

class ValidationTests(SimpleTestCase):
    def test_numeric_date_and_text_boundaries(self):
        for value in [True,None,'bad',float('nan'),float('inf'),-1]:
            with self.subTest(value=value),self.assertRaises(Invalid):number(value,'score')
        with self.assertRaises(Invalid):integer(1.2,'score')
        for value in ['',None,'x'*301]:
            with self.subTest(value=value),self.assertRaises(Invalid):text(value)
        for value in ['bad',None]:
            with self.subTest(value=value),self.assertRaises(Invalid):date(value)
        for value in ['2026-01-01T00:00:00','bad',None]:
            with self.subTest(value=value),self.assertRaises(Invalid):timestamp(value)
        self.assertEqual(timestamp('2026-01-01T12:00:00+12:00'),'2026-01-01T00:00:00+00:00')
    def test_log_rejects_malformed_or_ambiguous_events(self):
        for content in ['', 'missing', '[25:00:00] A has killed B from C','[01:00:00] A waved','[01:00:00] A has killed B','[01:00:00]  has killed B from C','[01:00:02] A has killed B from C\n[01:00:01] A has killed B from C']:
            with self.subTest(content=content),self.assertRaises(Invalid):parse_log(content,'2026-09-01')
        with self.assertRaises(Invalid):parse_log('[01:00:00] A has killed B from C','2026-09-01','')
        self.assertEqual(len(parse_log('\n[01:00:00] A has killed B from C\n','2026-09-01')),1)
    def test_update_rollback_preserves_existing_install(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);dest=root/'installed';dest.mkdir();(dest/'release.json').write_text('{"version":"1.0.0"}');(dest/'original').write_text('keep')
            archive=root/'release.zip'
            with zipfile.ZipFile(archive,'w') as bundle:bundle.writestr('new.py','new')
            manifest=root/'release.json';manifest.write_text(json.dumps({'version':'2.0.0','archive':'release.zip','sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}))
            replace=os.replace
            def fail_stage(src,dst):
                if Path(src).name=='stage':raise OSError('simulated failure')
                return replace(src,dst)
            with patch('guilds.updater.os.replace',side_effect=fail_stage),self.assertRaises(OSError):install_release(manifest,dest)
            self.assertEqual((dest/'original').read_text(),'keep');self.assertFalse((dest/'new.py').exists())
            self.assertEqual(install_release(manifest,dest)['installed'],'2.0.0')
            self.assertFalse(install_release(manifest,dest)['available'])
        with self.assertRaises(ValueError):version('invalid')
    def test_wsgi_and_asgi_entrypoints(self):
        from config.wsgi import application as wsgi
        from config.asgi import application as asgi
        self.assertTrue(callable(wsgi));self.assertTrue(callable(asgi))
    def test_settings_key_persistence_and_https_configuration(self):
        import runpy
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,{'OPENIQ_DATA_DIR':temp,'SECRET_KEY':'','DEBUG':'0','HTTPS':'1','TRUST_PROXY':'1'}):
            first=runpy.run_path(str(root/'config/settings.py'));second=runpy.run_path(str(root/'config/settings.py'))
            self.assertEqual(first['SECRET_KEY'],second['SECRET_KEY'])
            if os.name != 'nt':self.assertEqual((Path(temp)/'.secret-key').stat().st_mode&0o777,0o600)
            self.assertTrue(first['SECURE_SSL_REDIRECT']);self.assertEqual(first['SECURE_PROXY_SSL_HEADER'],('HTTP_X_FORWARDED_PROTO','https'))
    def test_empty_capture_lines_and_invalid_choice(self):
        from .capture import JsonLineTail
        from .modules.core import choice
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'log';path.write_text('\n {}\n\n');self.assertEqual(len(JsonLineTail(path).read()),1)
        with self.assertRaises(Invalid):choice('bad',['allowed'],'kind')
    def test_release_rejects_external_archives_symlinks_and_size_limits(self):
        from .updater import inspect_release
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);manifest=root/'manifest.json';archive=root/'bundle.zip'
            manifest.write_text(json.dumps({'version':'1.0.0','archive':'../external.zip','sha256':'unused'}))
            with self.assertRaises(ValueError):inspect_release(manifest,root/'install')
            for mode in ['symlink','entry_size','total_size']:
                with self.subTest(mode=mode):
                    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as bundle:
                        if mode=='symlink':
                            entry=zipfile.ZipInfo('link');entry.external_attr=0o120777<<16;bundle.writestr(entry,'target')
                        elif mode=='entry_size':bundle.writestr('huge',bytes(21*1024*1024))
                        else:
                            for index in range(6):bundle.writestr(str(index),bytes(18*1024*1024))
                    manifest.write_text(json.dumps({'version':'1.0.0','archive':'bundle.zip','sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}))
                    with self.assertRaises(ValueError):install_release(manifest,root/'install')
                    self.assertFalse((root/'install').exists())
