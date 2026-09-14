"""Small relational envelope; each domain module owns its validated payload schema."""
import uuid
from django.conf import settings
from django.db import models

class Guild(models.Model):
    name = models.CharField(max_length=80, unique=True)
    server_id = models.CharField(max_length=30, blank=True)
    region = models.CharField(max_length=12, default='NA')
    config = models.JSONField(default=dict)
    revision = models.PositiveIntegerField(default=0)
    def __str__(self): return self.name

class Access(models.Model):
    guild = models.ForeignKey(Guild, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=12, choices=[(x,x) for x in ['owner','admin','member']])
    class Meta:
        constraints = [models.UniqueConstraint(fields=['guild','user'],name='unique_access')]

class Record(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    guild = models.ForeignKey(Guild, on_delete=models.CASCADE)
    kind = models.CharField(max_length=30, db_index=True)
    key = models.CharField(max_length=180)
    data = models.JSONField(default=dict)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['guild','kind','key'],name='unique_record')]
        indexes = [models.Index(fields=['guild','kind'])]

class Audit(models.Model):
    guild = models.ForeignKey(Guild, on_delete=models.CASCADE)
    actor = models.CharField(max_length=150)
    action = models.CharField(max_length=80)
    data = models.JSONField(default=dict)
    created = models.DateTimeField(auto_now_add=True)

class Outbox(models.Model):
    guild = models.ForeignKey(Guild, on_delete=models.CASCADE)
    key = models.CharField(max_length=200, unique=True)
    channel = models.CharField(max_length=80, default='preview')
    text = models.TextField()
    status = models.CharField(max_length=15, default='preview')
    created = models.DateTimeField(auto_now_add=True)
    attempts = models.PositiveIntegerField(default=0)
    retry_at = models.DateTimeField(null=True, blank=True)
    lease_until = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=200, blank=True)


class RequestLimit(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    count = models.PositiveIntegerField(default=0)
    expires = models.PositiveBigIntegerField(db_index=True)
