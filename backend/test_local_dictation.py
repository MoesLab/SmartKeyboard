import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
from local_dictation import LocalDictation


class DictationTests(unittest.TestCase):
    def test_cloud_rejection_never_opens_audio(self):
        audio=Mock();controller=LocalDictation('/missing',audio)
        with self.assertRaisesRegex(ValueError,'Cloud'):controller.start({'mode':'cloud'})
        audio.status.assert_not_called()

    def test_missing_model_never_starts_capture(self):
        audio=Mock();controller=LocalDictation('/missing',audio)
        self.assertFalse(controller.availability()['localAvailable'])
        with self.assertRaises(ValueError):controller.start({'mode':'local'})
        audio.status.assert_not_called()

    def test_benchmark_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            app=Path(directory);(app/'.venv-stt/bin').mkdir(parents=True);(app/'.venv-stt/bin/python').touch()
            model=app/'models/vosk-model-small-en-us-0.15/am';model.mkdir(parents=True);(model/'final.mdl').touch()
            controller=LocalDictation(app,Mock());self.assertFalse(controller.availability()['localAvailable'])
            (app/'config').mkdir();(app/'config/local-stt.json').write_text(json.dumps({'version':1,'enabled':True}))
            self.assertTrue(controller.availability()['localAvailable'])
            (app/'config/local-stt.json').write_text(json.dumps({'version':1,'enabled':False}))
            self.assertFalse(controller.availability()['localAvailable'])

    def test_streamed_events_stay_local_and_aggregate(self):
        controller=LocalDictation('/missing',Mock());process=Mock()
        process.stdout=io.StringIO('\n'.join(json.dumps(e) for e in [{'kind':'ready'},{'kind':'partial','text':'first','level':40},{'kind':'final','text':'first words'},{'kind':'final','text':'second words'},{'kind':'done','message':'Review'}])+'\n')
        process.wait.return_value=0;controller.process=process
        controller._read(process)
        state=controller.snapshot();self.assertEqual(state['state'],'done');self.assertEqual(state['text'],'first words second words')
        self.assertIsNone(controller.process);self.assertEqual(state['level'],0)

    def test_stop_requests_graceful_worker_shutdown(self):
        controller=LocalDictation('/missing',Mock());process=Mock();process.pid=123;controller.process=process
        with patch('local_dictation.os.killpg',create=True) as kill:
            result=controller.stop();self.assertEqual(result['state'],'stopping');kill.assert_called_once()


if __name__=='__main__':unittest.main()
