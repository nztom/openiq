from django.apps import AppConfig


class GuildsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'guilds'

    def ready(self):
        from . import war_history
        from django.contrib.auth.signals import user_logged_in
        from .session_security import login_lifetime
        user_logged_in.connect(login_lifetime,dispatch_uid='openiq.login_lifetime')
