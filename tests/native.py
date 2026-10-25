"""Actual installed-framework integration, isolated synthetic identity/inference only."""
import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
(ROOT/'evidence').mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT))
from preview import prepare, make_runner

parser = argparse.ArgumentParser()
parser.add_argument('--hermes-source', required=True)
args = parser.parse_args()
home_context = tempfile.TemporaryDirectory(prefix='mira-native-test-', dir=ROOT.parent)
CONFIG = prepare(Path(home_context.name), Path(args.hermes_source).resolve(), 0)
logging.basicConfig(level=logging.CRITICAL)
from aiohttp import ClientSession
from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import BasePlatformAdapter
from gateway.platforms.event import MessageEvent
from hermes_cli.plugin_isolation import HOST_UNSUPPORTED_CTX_METHODS


class NativeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.runner, self.adapter, self.manager, self.version = make_runner(CONFIG)
        await self.adapter.connect()
        self.client = ClientSession(json_serialize=lambda value: json.dumps(value, ensure_ascii=False))
        self.headers = {'Origin':self.adapter.origin, 'X-Mira-Client':'1'}
        self.token = await self.pair('synthetic-alice')

    async def asyncTearDown(self):
        port = self.adapter.port
        await self.client.close()
        await self.adapter.disconnect()
        self.assertFalse(self.adapter.socket_path.exists())
        with socket.socket() as probe:
            self.assertNotEqual(probe.connect_ex(('127.0.0.1',port)), 0)

    async def request(self, path, method='GET', data=None, token=None, headers=None):
        hdr = dict(self.headers if headers is None else headers)
        if token is not None:
            hdr['Authorization']='Bearer '+token
        async with self.client.request(method, self.adapter.origin+path, json=data, headers=hdr) as result:
            return result.status, await result.json()

    async def pair(self, principal):
        code=self.adapter.new_pairing(principal)['code']
        status,data=await self.request('/api/pair','POST',{'code':code})
        self.assertEqual(status,200,data)
        return data['token']

    async def ticket(self, token=None):
        status,data=await self.request('/api/ticket','POST',{},token or self.token)
        self.assertEqual(status,200,data)
        return data['request_id']

    async def submit(self, text, token=None):
        ident=await self.ticket(token)
        status,data=await self.request('/api/requests','POST',{'request_id':ident,'text':text},token or self.token)
        self.assertEqual(status,200,data)
        return ident

    async def finish(self, ident, token=None, allowed=('answer','error','cancelled'), seconds=12):
        for _ in range(int(seconds*20)):
            status,data=await self.request('/api/requests/'+ident,token=token or self.token)
            self.assertEqual(status,200,data)
            if data['state'] in allowed:
                return data
            await asyncio.sleep(.05)
        self.fail('No confirmed terminal outcome: '+str(data))

    async def test_registration_native_followup_and_final_egress(self):
        self.assertIsInstance(self.adapter, BasePlatformAdapter)
        self.assertEqual(self.adapter.gateway_runner, self.runner)
        one=await self.submit('SYNTHETIC-NONCE-728')
        self.assertIn('SYNTHETIC-NONCE-728',(await self.finish(one))['answer'])
        two=await self.submit('fixture:followup')
        self.assertIn('SYNTHETIC-NONCE-728',(await self.finish(two))['answer'])
        calls=self.runner.synthetic_calls
        self.assertEqual(len(calls),2)
        self.assertEqual(calls[0]['session'],calls[1]['session'])
        self.assertTrue(all(not c['control'] for c in calls))
        result=await self.adapter.send(self.adapter.principals['synthetic-alice']['chat'],'PRIVATE proactive',metadata={'notify':True})
        self.assertFalse(result.success)

    async def test_missing_invalid_auth_origin_host_csrf_and_schema(self):
        self.assertEqual((await self.request('/api/current'))[0],401)
        self.assertEqual((await self.request('/api/current',token='SYNTHETIC-INVALID'))[0],401)
        for hdr in ({}, {'Origin':'https://attacker.invalid','X-Mira-Client':'1'},
                    {'Origin':self.adapter.origin,'X-Mira-Client':'1','Sec-Fetch-Site':'cross-site'},
                    {'Origin':self.adapter.origin,'X-Mira-Client':'1','Host':'attacker.invalid'}):
            self.assertEqual((await self.request('/api/ticket','POST',{},self.token,hdr))[0],403)
        self.assertEqual((await self.request('/api/ticket','POST',{'profile':'other'},self.token))[0],400)
        self.assertEqual((await self.request('/api/current?token=forbidden',token=self.token))[0],400)
        self.assertEqual((await self.request('/api/ticket','POST',{'large':'x'*9000},self.token))[0],413)

    async def test_pairing_single_use_expiry_revocation_and_native_allowlist(self):
        code=self.adapter.new_pairing('synthetic-alice')['code']
        self.assertEqual((await self.request('/api/current',token=self.token))[0],401)
        self.assertEqual((await self.request('/api/pair','POST',{'code':code}))[0],200)
        self.assertEqual((await self.request('/api/pair','POST',{'code':code}))[0],401)
        with self.assertRaises(Exception): self.adapter.new_pairing('attacker')
        code=self.adapter.new_pairing('synthetic-alice')['code']
        self.adapter.codes[self.adapter.digest(code)]['expires']=0
        self.assertEqual((await self.request('/api/pair','POST',{'code':code}))[0],401)
        self.token=await self.pair('synthetic-alice')
        self.adapter.grants[self.adapter.digest(self.token)]['expires']=0
        self.assertEqual((await self.request('/api/current',token=self.token))[0],401)
        self.token=await self.pair('synthetic-alice')
        self.adapter.config.extra['allowed_users']=['synthetic-bob']
        self.assertEqual((await self.request('/api/current',token=self.token))[0],403)
        self.assertNotIn(self.adapter.digest(self.token),self.adapter.grants)

    async def test_identity_session_profile_and_control_injection(self):
        bob=await self.pair('synthetic-bob')
        ident=await self.submit('alice private synthetic')
        await self.finish(ident)
        self.assertEqual((await self.request('/api/requests/'+ident,token=bob))[1]['state'],'unknown')
        status,_=await self.request('/api/requests','POST',{'request_id':ident,'text':'alice private synthetic'},bob)
        self.assertEqual(status,409)
        for field in ('principal','profile','session_id','chat_id','internal','metadata','allow_gateway_control'):
            body={'request_id':ident,'text':'probe',field:'forged'}
            self.assertEqual((await self.request('/api/requests','POST',body,self.token))[0],400)
        other=await self.submit('fixture:followup',bob)
        self.assertIn('no previous request',(await self.finish(other,bob))['answer'])
        command=await self.submit('/approve always')
        await self.finish(command)
        self.assertFalse(self.runner.synthetic_calls[-1]['control'])
        self.assertNotEqual(self.runner.synthetic_calls[0]['session'],self.runner.synthetic_calls[1]['session'])

    async def test_duplicate_and_conflict_exactly_one_native_dispatch(self):
        ident=await self.submit('fixture:delay')
        body={'request_id':ident,'text':'fixture:delay'}
        results=await asyncio.gather(*(self.request('/api/requests','POST',body,self.token) for _ in range(4)))
        self.assertTrue(all(s==200 for s,_ in results))
        self.assertEqual((await self.request('/api/requests','POST',{**body,'text':'changed'},self.token))[0],409)
        self.assertEqual((await self.request('/api/ticket','POST',{},self.token))[0],409)
        await self.finish(ident)
        self.assertEqual(len(self.runner.synthetic_calls),1)
        self.assertEqual((await self.request('/api/requests','POST',body,self.token))[1]['state'],'answer')
        self.assertEqual(len(self.runner.synthetic_calls),1)

    async def test_unknown_restart_and_retention_never_reexecute(self):
        ident=await self.submit('synthetic first')
        await self.finish(ident)
        self.adapter.records[ident]['created']-=1900
        self.adapter.sweep()
        self.assertEqual((await self.request('/api/requests/'+ident,token=self.token))[1]['state'],'unknown')
        self.assertEqual((await self.request('/api/requests','POST',{'request_id':ident,'text':'synthetic first'},self.token))[0],409)
        old_token=self.token
        await self.adapter.disconnect()
        # A NEW actual registry-created adapter and gateway, same isolated home.
        self.runner,self.adapter,self.manager,self.version=make_runner(CONFIG)
        await self.adapter.connect()
        self.headers['Origin']=self.adapter.origin
        self.assertEqual((await self.request('/api/current',token=old_token))[0],401)
        self.token=await self.pair('synthetic-alice')
        self.assertEqual((await self.request('/api/requests/'+ident,token=self.token))[1]['state'],'unknown')
        self.assertEqual((await self.request('/api/requests','POST',{'request_id':ident,'text':'synthetic first'},self.token))[0],409)
        self.assertEqual(len(self.runner.synthetic_calls),0)

    async def test_backend_timeout_cancel_and_recovery(self):
        ident=await self.submit('fixture:backend')
        self.assertEqual((await self.finish(ident))['state'],'error')
        self.adapter.timeout_seconds=1
        ident=await self.submit('fixture:delay')
        await asyncio.sleep(1.6)
        self.assertEqual((await self.request('/api/requests/'+ident,token=self.token))[1]['state'],'unknown')
        self.assertEqual((await self.request('/api/ticket','POST',{},self.token))[0],409)
        await self.finish(ident)
        ident=await self.submit('fixture:delay')
        await asyncio.sleep(.1)
        status,_=await self.request('/api/requests/'+ident+'/stop','POST',{},self.token)
        self.assertEqual(status,200)
        self.assertEqual((await self.finish(ident))['state'],'cancelled')

    async def test_approval_denied_and_final_only_projection(self):
        ident=await self.submit('fixture:approval')
        result=await self.finish(ident)
        self.assertEqual(result['state'],'error')
        self.assertNotIn('answer',result)
        ident=await self.submit('fixture:delay')
        chat=self.adapter.records[ident]['chat']
        for meta in ({}, {'notify':False}, {'notify':True,'is_approval_prompt':True}):
            self.assertFalse((await self.adapter.send(chat,'SECRET raw tool',reply_to=ident,metadata=meta)).success)
        self.assertNotIn('SECRET',json.dumps(self.adapter.view(self.adapter.records[ident])))
        await self.finish(ident)

    async def test_utf8_limits_and_long_answer(self):
        ident=await self.ticket()
        for text,status in [('é'*2049,400), ('é'*2048,200)]:
            self.assertEqual((await self.request('/api/requests','POST',{'request_id':ident,'text':text},self.token))[0],status)
        await self.finish(ident)
        ident=await self.submit('fixture:long')
        result=await self.finish(ident)
        self.assertGreater(len(result['answer'].encode()),3500)
        self.assertIn('漢字',result['answer'])

    async def test_operator_socket_permissions_and_repair_recovery(self):
        self.assertEqual(self.adapter.socket_path.stat().st_mode & 0o777,0o600)
        ident=await self.submit('fixture:delay')
        old_token=self.token
        reader,writer=await asyncio.open_unix_connection(str(self.adapter.socket_path))
        writer.write(b'{"action":"pair","principal":"synthetic-alice"}\n')
        await writer.drain()
        code=json.loads(await reader.readline())['code'];writer.close();await writer.wait_closed()
        status,data=await self.request('/api/pair','POST',{'code':code})
        self.assertEqual(status,200)
        self.token=data['token']
        self.assertEqual((await self.request('/api/current',token=old_token))[0],401)
        self.assertEqual((await self.request('/api/current',token=self.token))[1]['current']['request_id'],ident)
        await self.finish(ident)
        self.assertEqual(len(self.runner.synthetic_calls),1)

    async def test_reserved_ticket_lost_receipt_recovery_and_cancel(self):
        ident=await self.ticket()
        self.assertEqual((await self.request('/api/current',token=self.token))[1]['current']['state'],'reserved')
        self.assertEqual((await self.request('/api/requests/'+ident+'/stop','POST',{},self.token))[1]['state'],'cancelled')
        self.assertEqual((await self.request('/api/requests','POST',{'request_id':ident,'text':'too late'},self.token))[0],409)
        self.assertEqual(len(self.runner.synthetic_calls),0)
        self.assertNotEqual(await self.ticket(),ident)

    async def test_capacity_rate_limits_and_host_isolation_constraint(self):
        self.adapter.max_records=1
        ident=await self.submit('hello')
        await self.finish(ident)
        self.assertEqual((await self.request('/api/ticket','POST',{},self.token))[0],429)
        for _ in range(10): await self.request('/api/pair','POST',{'code':'SYNTHETIC-INVALID'})
        self.assertEqual((await self.request('/api/pair','POST',{'code':'SYNTHETIC-INVALID'}))[0],429)
        self.assertIn('register_platform',HOST_UNSUPPORTED_CTX_METHODS)
        with self.assertRaises(ValueError): type(self.adapter)(PlatformConfig(extra={'host':'0.0.0.0'}))
        original=self.runner.config.multiplex_profiles
        self.runner.config.multiplex_profiles=True
        other=type(self.adapter)(PlatformConfig(extra={'port':0}))
        other.gateway_runner=self.runner
        other.set_message_handler(self.runner._handle_message)
        other.set_authorization_check(lambda *args:True)
        with self.assertRaises(RuntimeError): await other.connect()
        self.runner.config.multiplex_profiles=original


if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(NativeTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    from hermes_cli.version_info import get_version_info
    receipt={'suite':'native-installed-framework','synthetic_inference':True,
             'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
             'passed':result.wasSuccessful(),'hermes_version':get_version_info().display_version,
             'live_model':False,'hardware':False}
    (ROOT/'evidence'/'native-tests.json').write_text(json.dumps(receipt,indent=2))
    home_context.cleanup()
    sys.exit(0 if result.wasSuccessful() else 1)
