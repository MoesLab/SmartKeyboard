import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from audio_preferences import selected, save, HEADSET, allowed_input
from headset_audio import HeadsetAudio, parse_devices
from cloud_transcription import transcribe


class CloudTests(unittest.TestCase):
    def test_pcm_uploaded_as_wav_only_to_fixed_tls_endpoint(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root)/'openai-api-key').write_text('sk-test-private')
            connection=Mock();response=Mock(status=200);response.read.return_value=b'{"text":"tap the button"}';connection.getresponse.return_value=response
            with patch('cloud_transcription.http.client.HTTPSConnection',return_value=connection) as factory:
                self.assertEqual(transcribe(root,b'\0\0'*100)['text'],'tap the button')
            self.assertEqual(factory.call_args.args[0],'api.openai.com')
            call=connection.request.call_args
            self.assertEqual(call.args[:2],('POST','/v1/audio/transcriptions'))
            self.assertIn(b'RIFF',call.args[2]);self.assertIn(b'gpt-transcribe',call.args[2])
            self.assertNotIn(b'sk-test-private',call.args[2])
            self.assertEqual(connection.request.call_count,1);connection.close.assert_called_once()

    def test_cloud_errors_never_expose_key_or_retry(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root)/'openai-api-key').write_text('sk-test-private')
            connection=Mock();response=Mock(status=429);response.read.return_value=b'secret error';connection.getresponse.return_value=response
            with patch('cloud_transcription.http.client.HTTPSConnection',return_value=connection):
                with self.assertRaisesRegex(ValueError,'HTTP 429') as error:transcribe(root,b'00')
            self.assertNotIn('sk-test',str(error.exception));self.assertEqual(connection.request.call_count,1)

    def test_empty_oversized_odd_recording_never_connects(self):
        with patch('cloud_transcription.http.client.HTTPSConnection') as connection:
            for pcm in (b'',b'0',b'0'*1920002):
                with self.assertRaises(ValueError):transcribe('/missing',pcm)
            connection.assert_not_called()


class InputTests(unittest.TestCase):
    def test_headset_preferred_and_usb_choice_persisted_without_fallback(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(selected(root),HEADSET)
            name='alsa_input.usb-Test_Mic-00.mono-fallback'
            save(root,name);self.assertEqual(selected(root),name)
            save(root,HEADSET);self.assertEqual(selected(root),HEADSET)

    def test_only_real_usb_or_known_headset_inputs(self):
        for name in ('alsa_input.HDMI','bluez_source.OTHER','alsa_input.usb-mic.monitor','monitor',None):
            self.assertFalse(allowed_input(name))
        text='''Source #1
    Name: alsa_input.usb-Test-00.mono-fallback
    Description: USB Handheld
    Mute: no
    Volume: mono: 32768 / 50% / -18.06 dB
Source #2
    Name: alsa_output.usb-Test.monitor
    Description: Monitor
    Mute: no
    Volume: mono: 32768 / 50% / -18.06 dB
'''
        devices=parse_devices(text,'input');self.assertEqual(len(devices),1)
        self.assertEqual(devices[0]['description'],'USB Handheld')

    def test_undetected_usb_choice_is_rejected(self):
        helper=HeadsetAudio(None,Mock(return_value=''))
        with self.assertRaises(ValueError):helper.choose_input({'name':'alsa_input.usb-unknown'})


if __name__=='__main__':unittest.main()
