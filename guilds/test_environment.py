from django.test import SimpleTestCase
from .management.commands.validate_environment import problems


class EnvironmentTests(SimpleTestCase):
    def test_production_requires_oauth_and_rejects_demo_and_password_login(self):
        errors=problems({'SEED_DEMO':'1','ALLOW_LOCAL_LOGIN':'1'},False)
        self.assertTrue(any('DISCORD_CLIENT_SECRET' in error for error in errors))
        self.assertTrue(any('seeding' in error for error in errors))
        self.assertEqual(problems({'DISCORD_CLIENT_ID':'123','DISCORD_CLIENT_SECRET':'private','DISCORD_REDIRECT_URI':'https://guild.example/auth/discord/callback/','HTTPS':'1','ALLOWED_HOSTS':'guild.example'},False),[])
        self.assertEqual(problems({},False,'backup'),[])
        self.assertEqual(problems({'ALLOW_LOCAL_LOGIN':'1','SEED_DEMO':'1'},True),[])

    def test_invalid_boolean_delivery_and_sync_are_rejected_without_secrets(self):
        errors=problems({'ENABLE_DISCORD_DELIVERY':'1','DEBUG':'yes','RUN_SCHEDULER':'yes','DISCORD_SYNC_GLOBAL':'1','DISCORD_SYNC_GUILD':'123'},True)
        self.assertEqual(len(errors),4)
        self.assertEqual(problems({'RUN_SCHEDULER':'1','SCHEDULER_INTERVAL':'0'},True),['SCHEDULER_INTERVAL must be from 1 to 86400 seconds'])

    def test_unsafe_hosts_tls_origins_and_hsts_are_rejected(self):
        errors=problems({'ALLOWED_HOSTS':'*','CSRF_TRUSTED_ORIGINS':'http://bad.example','HSTS_SECONDS':'-1'},False)
        self.assertTrue(any('ALLOWED_HOSTS' in e for e in errors));self.assertTrue(any('HTTPS=1' in e for e in errors))
        self.assertTrue(any('origins' in e for e in errors));self.assertTrue(any('HSTS_SECONDS' in e for e in errors))
