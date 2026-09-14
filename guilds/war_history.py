"""Capture only wars actually changed inside a shared service transaction."""
from contextlib import contextmanager
from contextvars import ContextVar
from django.db.models.signals import pre_save, post_save, pre_delete
from django.dispatch import receiver
from .models import Record
from .modules.core import now, ident

_actor = ContextVar('war_history_actor', default=None)


@contextmanager
def recording(user, module, action):
    # Privacy scrubbing must not recreate removed data in a new history entry.
    value = None if module == 'privacy' or (module, action) == ('admin', 'disband') else (user.username, module+'.'+action)
    token = _actor.set(value)
    try:
        yield
    finally:
        _actor.reset(token)


def revision(instance, before, after, using):
    actor, action = _actor.get()
    Record.objects.using(using).create(guild_id=instance.guild_id, kind='war_revision', key=ident(),
        data={'war': instance.key, 'actor': actor, 'action': action, 'at': now(), 'before': before, 'after': after})


@receiver(pre_save, sender=Record)
def before_save(sender, instance, using, **kwargs):
    if instance.kind == 'war' and _actor.get():
        instance._war_before = Record.objects.using(using).filter(pk=instance.pk).values_list('data', flat=True).first()


@receiver(post_save, sender=Record)
def after_save(sender, instance, using, **kwargs):
    if instance.kind == 'war' and _actor.get() and instance._war_before != instance.data:
        revision(instance, instance._war_before, instance.data, using)


@receiver(pre_delete, sender=Record)
def before_delete(sender, instance, using, **kwargs):
    if instance.kind == 'war' and _actor.get():
        revision(instance, instance.data, None, using)
