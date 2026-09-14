"""Shared checksum and format validation for database snapshots."""
import hashlib,json
from django.core.management.base import CommandError


def validate_snapshot(source):
    try:
        manifest=json.loads((source/'manifest.json').read_text())
        if manifest['format']!='openiq-backup-v1':
            raise ValueError()
        engine=manifest.get('engine','django.db.backends.sqlite3')
        filename='db.sqlite3' if engine=='django.db.backends.sqlite3' else 'database.dump' if engine=='django.db.backends.postgresql' else None
        if filename is None or set(manifest['sha256'])!={filename,'.secret-key'}:
            raise ValueError()
        for name,digest in manifest['sha256'].items():
            path=source/name
            if path.is_symlink() or not path.is_file():
                raise ValueError()
            with path.open('rb') as stream:
                if hashlib.file_digest(stream,'sha256').hexdigest()!=digest:
                    raise ValueError()
        return manifest,filename
    except (OSError,ValueError,KeyError,TypeError):raise CommandError('Invalid backup manifest, file type, or checksum') from None

