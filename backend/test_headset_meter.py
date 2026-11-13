import io
import struct
import time
import unittest
import wave
from unittest.mock import Mock,patch
from headset_audio import HeadsetAudio,make_test_tone,measure_pcm


class HeadsetMeterTests(unittest.TestCase):
    def helper(self):
        helper=HeadsetAudio(None,runner=Mock())
        helper.session_prefix=['session']
        helper.status=Mock(return_value={'outputs':[{'name':'bluez_sink.C0_86_B3_F2_E8_96.headset_head_unit'}],
                                         'inputs':[{'name':'bluez_source.C0_86_B3_F2_E8_96.headset_head_unit'}]})
        return helper

    def test_generated_tone_is_short_and_low_amplitude(self):
        with wave.open(io.BytesIO(make_test_tone()),'rb') as wav:
            self.assertEqual(wav.getnchannels(),1);self.assertEqual(wav.getframerate(),16000)
            self.assertAlmostEqual(wav.getnframes()/16000,0.55)
            samples=[s[0] for s in struct.iter_unpack('<h',wav.readframes(wav.getnframes()))]
            self.assertLessEqual(max(map(abs,samples)),3277);self.assertGreater(max(samples),3000)

    def test_pcm_meter_reacts_to_signal(self):
        self.assertEqual(measure_pcm(bytes(1600)),(0,-60))
        quiet=measure_pcm(struct.pack('<h',100)*800)[0]
        speech=measure_pcm(struct.pack('<h',3000)*800)[0]
        loud=measure_pcm(struct.pack('<h',30000)*800)[0]
        self.assertLess(quiet,speech);self.assertLess(speech,loud)

    def test_test_tone_is_targeted_and_does_not_change_volume(self):
        helper=self.helper();name=helper.status()['outputs'][0]['name']
        with patch('headset_audio.shutil.which',return_value='/usr/bin/paplay'),patch('headset_audio.subprocess.run') as run:
            helper.play_test({'name':name})
            self.assertEqual(run.call_args.args[0],['session','/usr/bin/paplay','--device='+name])
            self.assertTrue(run.call_args.kwargs['input'].startswith(b'RIFF'))
        helper.run.assert_not_called()
        with self.assertRaises(ValueError):helper.play_test({'name':'alsa_output.HDMI'})

    def test_meter_requires_explicit_valid_source_and_has_deadline(self):
        helper=self.helper();process=Mock();name=helper.status()['inputs'][0]['name']
        with patch('headset_audio.shutil.which',return_value='/usr/bin/parec'),patch('headset_audio.subprocess.Popen',return_value=process) as launch,patch('headset_audio.threading.Thread'):
            result=helper.start_meter({'name':name});self.assertTrue(result['active'])
            command=launch.call_args.args[0];self.assertIn('--device='+name,command);self.assertIn('--raw',command)
            self.assertTrue(launch.call_args.kwargs['start_new_session'])
            self.assertGreater(helper.meter_deadline,time.monotonic())
            self.assertFalse(helper.stop_meter()['active']);self.assertIsNone(helper.meter_process)
        with self.assertRaises(ValueError):helper.start_meter({'name':name+'.monitor'})

    def test_lost_page_expires_capture_without_more_audio_data(self):
        helper=self.helper();process=Mock();helper.meter_process=process;helper.meter_deadline=time.monotonic()-1
        with patch.object(helper,'_terminate_capture') as stop:
            helper._read_meter(process);stop.assert_called_once_with(process)
        self.assertIsNone(helper.meter_process);process.stdout.close.assert_called_once()


if __name__=='__main__':unittest.main()
