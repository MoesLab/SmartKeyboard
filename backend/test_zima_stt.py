import http.client
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
from http.server import ThreadingHTTPServer

from zima_stt_server import handler_for, MAX_AUDIO
from zima_dictation_worker import load_pairing
from local_dictation import LocalDictation


class EndpointTests(unittest.TestCase):
    def setUp(self):
        self.calls=[]
        self.config={'client':'192.168.0.17','token':'a'*64}
        def transcribe(pcm):
            self.calls.append(pcm)
            return {'text':'hello world'}
        self.server=ThreadingHTTPServer(('127.0.0.1',0),handler_for(self.config,transcribe))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()

    def send(self,path,body=b'',authorized=True,headers=None):
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=3)
        values={'Content-Type':'application/octet-stream'}
        if authorized: values['Authorization']='Bearer '+'a'*64
        values.update(headers or {})
        connection.request('POST',path,body,values)
        response=connection.getresponse(); code=response.status; payload=json.loads(response.read())
        connection.close(); return code,payload

    def test_unauthorized_audio_never_reaches_model(self):
        self.assertEqual(self.send('/transcribe',b'\0\0',False)[0],401)
        self.assertEqual(self.calls,[])

    def test_valid_health_and_audio(self):
        self.assertTrue(self.send('/health')[1]['ready'])
        self.assertEqual(self.send('/transcribe',b'\0\0')[1]['text'],'hello world')
        self.assertEqual(self.calls,[b'\0\0'])

    def test_empty_odd_oversized_wrong_type_rejected(self):
        for body in (b'',b'1'):
            self.assertEqual(self.send('/transcribe',body)[0],400)
        self.assertEqual(self.send('/transcribe',b'',headers={'Content-Length':str(MAX_AUDIO+2)})[0],400)
        self.assertEqual(self.send('/transcribe',b'00',headers={'Content-Type':'text/plain'})[0],415)
        self.assertEqual(self.calls,[])

    def test_busy_rejects_without_duplicate_recognition(self):
        entered=threading.Event(); release=threading.Event()
        def transcribe(pcm):
            entered.set(); release.wait(3); return {'text':'one'}
        other=ThreadingHTTPServer(('127.0.0.1',0),handler_for(self.config,transcribe))
        thread=threading.Thread(target=other.serve_forever,daemon=True); thread.start()
        original=self.server; self.server=other
        results=[]
        caller=threading.Thread(target=lambda:results.append(self.send('/transcribe',b'00')))
        caller.start()
        try:
            self.assertTrue(entered.wait(2))
            self.assertEqual(self.send('/transcribe',b'00')[0],503)
        finally:
            release.set(); caller.join(); other.shutdown(); other.server_close(); thread.join(); self.server=original
        self.assertEqual(results[0][0],200)


class PairingTests(unittest.TestCase):
    def config(self,root):
        path=Path(root)/'zima-stt.json'
        data={'version':1,'enabled':True,'host':'192.168.0.16','port':8766,'token':'a'*64,'certificate':'TEST'}
        path.write_text(json.dumps(data)); return path,data

    @patch('zima_dictation_worker.ssl.create_default_context')
    def test_pairing_rejects_public_host_bad_token_disabled(self,context):
        with tempfile.TemporaryDirectory() as root:
            path,data=self.config(root)
            self.assertEqual(load_pairing(path)['host'],'192.168.0.16')
            for key,value in [('host','8.8.8.8'),('host','127.0.0.1'),('host','169.254.1.1'),('token','x'*64),('enabled',False)]:
                changed=dict(data);changed[key]=value;path.write_text(json.dumps(changed))
                with self.assertRaises(ValueError):load_pairing(path)

    @patch('zima_dictation_worker.ssl.create_default_context')
    def test_zima_config_available_without_radxa_model(self,context):
        with tempfile.TemporaryDirectory() as root:
            config=Path(root)/'config';config.mkdir();path,data=self.config(config)
            controller=LocalDictation(root,Mock())
            self.assertTrue(controller.availability()['localAvailable'])
            self.assertEqual(controller.availability()['engine'],'zima')
            data['enabled']=False;path.write_text(json.dumps(data))
            self.assertFalse(controller.availability()['localAvailable'])

    def test_processing_heartbeat_and_result_state(self):
        controller=LocalDictation('/missing',Mock());process=Mock()
        process.stdout=io.StringIO('\n'.join(json.dumps(e) for e in [
            {'kind':'processing','message':'Working'}, {'kind':'final','text':'hello'}, {'kind':'done'}])+'\n')
        process.wait.return_value=0;controller.process=process
        controller._read(process)
        self.assertEqual(controller.snapshot()['text'],'hello')
        self.assertEqual(controller.snapshot()['state'],'done')

    @patch('zima_dictation_worker.subprocess.Popen')
    @patch('zima_dictation_worker.request',side_effect=OSError('offline'))
    @patch('zima_dictation_worker.load_pairing',return_value={})
    def test_unreachable_server_never_opens_microphone(self,pairing,request,popen):
        import zima_dictation_worker
        with patch('sys.argv',['worker','--config','missing']),patch('sys.stdout',new_callable=io.StringIO):
            self.assertEqual(zima_dictation_worker.main(),1)
        popen.assert_not_called()


if __name__=='__main__':unittest.main()
