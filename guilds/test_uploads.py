import io,tempfile,shutil
from functools import partial
from unittest import skipUnless
from pathlib import Path
from unittest.mock import Mock,patch
from PIL import Image
from django.test import SimpleTestCase
from django.core.files.uploadhandler import StopUpload
from .uploads import BoundedUploads
from .modules.integrations import ocr
from .modules.core import Invalid


class UploadTests(SimpleTestCase):
    def test_signature_verification_and_timeout_error(self):
        with self.assertRaises(Invalid):ocr(b'<svg>not a raster image</svg>')
        image=Image.new('RGB',(20,20),'white');data=io.BytesIO();image.save(data,format='GIF');image.close()
        with self.assertRaises(Invalid):ocr(data.getvalue())
        image=Image.new('RGB',(20,20),'white');data=io.BytesIO();image.save(data,format='PNG');image.close()
        with patch('pytesseract.image_to_string',side_effect=RuntimeError('private temp path')) as engine,self.assertRaisesMessage(Invalid,'timed out'):
            ocr(data.getvalue(),timeout=2)
        self.assertEqual(engine.call_args.kwargs['timeout'],2)

    @skipUnless(shutil.which('tesseract'),'Requires the local Tesseract engine')
    def test_real_engine_cleans_its_temporary_files(self):
        image=Image.new('RGB',(20,20),'white');data=io.BytesIO();image.save(data,format='PNG');image.close()
        with tempfile.TemporaryDirectory() as directory,patch('pytesseract.pytesseract.NamedTemporaryFile',partial(tempfile.NamedTemporaryFile,dir=directory)):
            ocr(data.getvalue())
            self.assertEqual(list(Path(directory).iterdir()),[])

    def test_aggregate_stream_limit_does_not_reset_between_files(self):
        request=Mock();handler=BoundedUploads(request)
        handler.receive_data_chunk(b'x'*(7*1024*1024),0)
        handler.file_complete(7*1024*1024)
        with self.assertRaises(StopUpload):handler.receive_data_chunk(b'x'*(6*1024*1024),0)
        self.assertTrue(request.upload_too_large)
