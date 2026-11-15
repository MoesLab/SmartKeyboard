import io
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import Mock,patch
import wave
import dictation_ready as cue
from audio_preferences import HEADSET


class ReadyCueTests(unittest.TestCase):
    def test_tone_is_short_and_not_clipped(self):
        with wave.open(io.BytesIO(cue.ready_tone()),'rb') as wav:
            self.assertEqual((wav.getnchannels(),wav.getsampwidth(),wav.getframerate()),(1,2,16000))
            self.assertAlmostEqual(wav.getnframes()/16000,0.21)
            samples=[value[0] for value in struct.iter_unpack('<h',wav.readframes(wav.getnframes()))]
        self.assertLessEqual(max(map(abs,samples)),4000)

    def test_usb_has_no_surprise_headset_sound(self):
        with patch.object(cue.subprocess,'Popen') as playback:
            self.assertIsNone(cue.prepare_headset(Mock(),'alsa_input.usb-test',lambda:False))
            playback.assert_not_called()

    def test_no_ready_tone_when_microphone_closes(self):
        microphone=Mock();microphone.stdout.fileno.return_value=10
        with patch.object(cue.select,'select',return_value=([microphone.stdout],[],[])),patch.object(cue.os,'read',return_value=b''),patch.object(cue.subprocess,'Popen') as playback:
            with self.assertRaises(ValueError):cue.prepare_headset(microphone,HEADSET,lambda:False)
            playback.assert_not_called()

    def test_direct_worker_excludes_warmup_and_tone_from_upload(self):
        import zima_dictation_worker as worker
        with tempfile.TemporaryDirectory() as root:
            (Path(root)/'openai-api-key').write_text('sk-private-test')
            microphone=Mock();microphone.stdout.fileno.return_value=10
            playback=Mock();playback.returncode=0;playback.poll.side_effect=[None,0,0]
            count=0;worker.STOP=False
            def readable(*unused):
                nonlocal count
                count+=1
                if count==4:worker.STOP=True
                return ([microphone.stdout],[],[])
            speech=b'\1\0'*100
            try:
                with patch('sys.argv',['worker','--direct-key-dir',root,'--mode','cloud','--source',HEADSET]), \
                     patch.object(worker.signal,'signal'), \
                     patch.object(worker.subprocess,'Popen',side_effect=[microphone,playback]) as launch, \
                     patch.object(worker.select,'select',side_effect=readable), \
                     patch.object(worker.os,'read',side_effect=[b'\2\0'*100,b'\3\0'*100,speech,b'']), \
                     patch('cloud_transcription.transcribe',return_value={'text':'hello'}) as cloud, \
                     patch('sys.stdout',new_callable=io.StringIO):
                    self.assertEqual(worker.main(),0)
                    self.assertEqual(cloud.call_args.args[1],speech)
                    self.assertIn('--device=bluez_sink.C0_86_B3_F2_E8_96.headset_head_unit',launch.call_args_list[1].args[0])
            finally:worker.STOP=False


if __name__=='__main__':unittest.main()
