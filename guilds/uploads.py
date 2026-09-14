from django.core.files.uploadhandler import FileUploadHandler,StopUpload


class BoundedUploads(FileUploadHandler):
    """Bound aggregate file bytes while streaming, including requests without a size."""
    def __init__(self,request=None):super().__init__(request);self.received=0
    def receive_data_chunk(self,raw_data,start):
        self.received+=len(raw_data)
        if self.received>12*1024*1024:
            self.request.upload_too_large=True
            raise StopUpload(connection_reset=True)
        return raw_data
    def file_complete(self,file_size):return None
