import asyncio
import json
from unittest.mock import AsyncMock,Mock
import httpx
from django.core.exceptions import ObjectDoesNotExist,PermissionDenied
from django.test import SimpleTestCase
from .discord_responses import respond,error_message,command_result
from .modules.core import Invalid


class ResponseTests(SimpleTestCase):
    def test_command_results_hide_internal_gear_record_fields(self):
        record={'id':'uuid','member':'member-1','ap':999,'aap':998,'dp':997,'score':1996,'at':'2026-09-16T00:00:00+00:00','current':True}
        update=command_result('gearupdate',record,{'member-1':'TestMember'})
        self.assertEqual(update,'Gear updated for TestMember.\nAP: 999\nAAP: 998\nDP: 997\nScore: 1996')
        self.assertNotIn('uuid',update);self.assertNotIn('2026',update)
        lookup=command_result('gear',{'gear':record},{'member-1':'TestMember'})
        self.assertTrue(lookup.startswith('Gear for TestMember.'))
        self.assertEqual(command_result('gear',{'gear':None}),'No gear has been recorded for this member yet.')
        listing=command_result('gearlist',{'gear':[record]},{'member-1':'TestMember'})
        self.assertIn('• TestMember — AP 999 / AAP 998 / DP 997 (Score 1996)',listing)
        self.assertEqual(command_result('setup',{'added':1,'inactive':0}),'Roster updated.\nAdded: 1\nMarked inactive: 0')

    def test_readable_private_results_and_nontruncated_files(self):
        interaction=Mock();interaction.followup.send=AsyncMock()
        asyncio.run(respond(interaction,{'wars':2,'teams':['Front'],'status':'saved'}))
        self.assertIn('Wars: 2',interaction.followup.send.call_args.args[0])
        self.assertTrue(interaction.followup.send.call_args.kwargs['ephemeral'])
        asyncio.run(respond(interaction,'@everyone **bold**'))
        self.assertNotIn('@everyone',interaction.followup.send.call_args.args[0])
        asyncio.run(respond(interaction,{}));self.assertEqual(interaction.followup.send.call_args.args[0],'Done.')
        asyncio.run(respond(interaction,[1,2]));self.assertIn('1',interaction.followup.send.call_args.args[0])
        captured=[]
        async def capture(*args,**kwargs):captured.append(json.loads(kwargs['file'].fp.read()))
        interaction.followup.send=AsyncMock(side_effect=capture)
        result={'full':'😀'*1500};asyncio.run(respond(interaction,result));self.assertEqual(captured,[result])
        interaction.followup.send=AsyncMock()
        asyncio.run(respond(interaction,'x'*(8*1024*1024+1)))
        self.assertIn('exceeds',interaction.followup.send.call_args.args[0])

    def test_errors_do_not_expose_internal_details(self):
        self.assertEqual(error_message(Invalid('Choose a team')),'Choose a team')
        self.assertEqual(error_message(Invalid('member not found')),'That member was not found. Choose one from the command autocomplete list.')
        for error in [PermissionDenied('secret'),ObjectDoesNotExist('secret'),ValueError('secret'),httpx.ConnectError('secret')]:
            self.assertNotIn('secret',error_message(error))
        with self.assertLogs('guilds.discord_responses',level='ERROR') as logs:
            message=error_message(RuntimeError('password=secret'))
        self.assertIn('reference',message);self.assertNotIn('secret',message+' '.join(logs.output))
