import io,json,tempfile
from pathlib import Path
import httpx
from unittest.mock import Mock,patch
from django.test import TestCase
from django.core.management import call_command,CommandError
from .models import Guild
from .modules.commands import COMMANDS
from .management.commands.bot_diagnostics import permissions_for


class BotDiagnosticsTests(TestCase):
    def test_read_only_report_and_missing_permissions(self):
        g=Guild.objects.create(name='Diagnostics',server_id='100',config={'channels':{'bot':'300','unused':''},'welcome':{'role_ids':{'Raider':'400'}}})
        values=[{'id':'200'},{'id':'500'},{'id':'100'}, {'user':{'id':'200'},'roles':['600']},
                [{'id':'600','position':10,'permissions':str((1<<28)|(1<<10)|(1<<11)|(1<<14)|(1<<16))},{'id':'400','position':1,'permissions':'0'}],
                [{'id':'300','permission_overwrites':[{'id':'200','type':1,'allow':'0','deny':str(1<<11)}]}],
                [{'name':c} for c in {name.split(' ')[0] for name in COMMANDS}]]
        responses=[]
        for value in values:
            response=Mock();response.json.return_value=value;responses.append(response)
        output=io.StringIO()
        with patch.dict('os.environ',{'DISCORD_BOT_TOKEN':'secret','DISCORD_SYNC_GUILD':''}),patch('httpx.Client') as factory:
            client=factory.return_value.__enter__.return_value;client.get.side_effect=responses
            call_command('bot_diagnostics',guild=g.pk,stdout=output)
            client.post.assert_not_called();client.put.assert_not_called();client.patch.assert_not_called()
        report=json.loads(output.getvalue());checks=report['guilds'][0]['checks']
        self.assertTrue(checks['welcome_roles']['Raider']);self.assertFalse(checks['channels']['bot']['send'])
        self.assertNotIn('unused',checks['channels']);self.assertEqual(checks['missing_commands'],[]);self.assertNotIn('secret',output.getvalue())

    def test_requires_token_and_administrator_overrides(self):
        with patch.dict('os.environ',{'DISCORD_BOT_TOKEN':'','DISCORD_BOT_TOKEN_FILE':''}),self.assertRaises(CommandError):call_command('bot_diagnostics')
        self.assertTrue(permissions_for('100',[{'id':'100','permissions':'8'}],{'roles':[]}) & (1<<28))

    def test_reads_docker_secret_file(self):
        with tempfile.TemporaryDirectory() as directory:
            token_file=Path(directory)/'discord-token'
            token_file.write_text('secret\n')
            with patch.dict('os.environ',{'DISCORD_BOT_TOKEN':'','DISCORD_BOT_TOKEN_FILE':str(token_file)}),patch('httpx.Client') as factory:
                factory.return_value.__enter__.return_value.get.side_effect=httpx.ConnectError('offline')
                with self.assertRaisesMessage(CommandError,'Cannot verify the bot token/application'):
                    call_command('bot_diagnostics')
                authorization=factory.call_args.kwargs['headers']['Authorization']
                self.assertEqual(authorization,'Bot secret')
