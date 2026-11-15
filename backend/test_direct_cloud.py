import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
from local_dictation import LocalDictation


class DirectCloudTests(unittest.TestCase):
    def test_direct_cloud_ready_without_zima_or_local_model(self):
        with tempfile.TemporaryDirectory() as root:
            config=Path(root)/'config';config.mkdir()
            (config/'cloud-stt.json').write_text('{"enabled":true,"route":"direct"}')
            (config/'openai-api-key').write_text('sk-private-test')
            controller=LocalDictation(root,Mock())
            status=controller.availability()
            self.assertTrue(status['cloudAvailable']);self.assertFalse(status['localAvailable'])
            (config/'zima-stt.json').write_text('broken pairing')
            self.assertTrue(controller.availability()['cloudAvailable'])
            (config/'cloud-stt.json').write_text('{"enabled":false,"route":"direct"}')
            self.assertFalse(controller.availability()['cloudAvailable'])

    def test_direct_uses_system_python_with_low_memory_and_no_local_model(self):
        source='alsa_input.usb-Test-00.mono-fallback'
        audio=Mock();audio.session_prefix=[];audio.status.return_value={'inputs':[{'name':source}]};audio.check.active=False
        controller=LocalDictation('/app',audio)
        with patch.object(controller,'availability',return_value={'cloudAvailable':True,'localAvailable':False}), \
             patch.object(controller,'cloud_route',return_value='direct'), \
             patch('local_dictation.selected',return_value=source), \
             patch('local_dictation.Path.exists',return_value=True), \
             patch('local_dictation.Path.read_text',return_value='MemAvailable: 100000 kB'), \
             patch('local_dictation.threading.Thread'), \
             patch('local_dictation.subprocess.Popen') as process:
            controller.start({'mode':'cloud'})
            command=process.call_args.args[0]
            self.assertEqual(command[0],'/usr/bin/python3');self.assertIn('--direct-key-dir',command)
            self.assertNotIn('--config',command);self.assertNotIn('--model',command)

    def test_direct_capture_calls_cloud_without_lan_health_or_model(self):
        import zima_dictation_worker as worker
        with tempfile.TemporaryDirectory() as root:
            (Path(root)/'openai-api-key').write_text('sk-private-test')
            process=Mock();process.stdout.fileno.return_value=42;reads=0
            def ready(*args):
                nonlocal reads
                reads+=1
                if reads==2:worker.STOP=True
                return ([process.stdout],[],[])
            worker.STOP=False
            try:
                with patch('sys.argv',['worker','--direct-key-dir',root,'--mode','cloud','--source','alsa_input.usb-Test']), \
                     patch.object(worker,'request') as lan, \
                     patch.object(worker.signal,'signal'), \
                     patch.object(worker.subprocess,'Popen',return_value=process), \
                     patch.object(worker.select,'select',side_effect=ready), \
                     patch.object(worker.os,'read',side_effect=[b'\0\0'*100,b'']), \
                     patch('cloud_transcription.transcribe',return_value={'text':'direct speech'}) as cloud, \
                     patch('sys.stdout',new_callable=io.StringIO) as output:
                    self.assertEqual(worker.main(),0)
                    lan.assert_not_called();cloud.assert_called_once()
                    self.assertIn('direct speech',output.getvalue())
                    self.assertNotIn('sk-private-test',output.getvalue())
            finally:worker.STOP=False


if __name__=='__main__':unittest.main()
