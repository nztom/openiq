from datetime import datetime, timezone
from django.db import migrations


def import_delivery_state(apps, schema_editor):
    """Adopt the PR queue's metadata without retrying an ambiguous remote write."""
    Outbox = apps.get_model('guilds', 'Outbox')
    Record = apps.get_model('guilds', 'Record')
    database = schema_editor.connection.alias
    for record in Record.objects.using(database).filter(kind__in=['delivery_retry', 'delivery_pending']):
        if not record.key.isdecimal():
            continue
        item = Outbox.objects.using(database).filter(pk=int(record.key), guild_id=record.guild_id).first()
        if item is None:
            continue
        data = record.data
        if record.kind == 'delivery_pending' or data.get('lease_until', 0):
            item.status = 'uncertain'
            item.lease_until = None
            item.last_error = 'Previous queue may have sent this message; reconcile before retrying'
        elif item.status == 'preview' and data.get('next_attempt', 0):
            item.status = 'retry'
            item.attempts = data.get('attempts', 0)
            item.retry_at = datetime.fromtimestamp(data['next_attempt'], timezone.utc)
        item.save(using=database)


class Migration(migrations.Migration):
    dependencies = [
        ('guilds', '0002_requestlimit'),
        ('guilds', '0002_outbox_attempts_outbox_last_error_outbox_lease_until_and_more'),
    ]
    operations = [migrations.RunPython(import_delivery_state, migrations.RunPython.noop)]
