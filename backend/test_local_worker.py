import contextlib
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock,patch
import wave
import local_dictation_worker as worker


class Recognizer:
    def __init__(self,*args):pass
    def AcceptWaveform(self,data):return False
    def PartialResult(self):return json.dumps({'partial':'one two'})
    def FinalResult(self):return json.dumps({'text':'one two'})


class WorkerTests(unittest.TestCase):
    def fake_vosk(self):return types.SimpleNamespace(Model=lambda path:object(),KaldiRecognizer=Recognizer,SetLogLevel=lambda level:None)

    def test_file_benchmark_never_opens_a_microphone(self):
        with tempfile.TemporaryDirectory() as directory:
            sample=Path(directory)/'sample.wav'
            with wave.open(str(sample),'wb') as wav:
                wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(16000);wav.writeframes(bytes(3200))
            output=io.StringIO();resource=types.SimpleNamespace(RUSAGE_SELF=0,getrusage=lambda kind:types.SimpleNamespace(ru_maxrss=102400))
            with patch.object(worker,'tune'),patch.dict(sys.modules,{'vosk':self.fake_vosk(),'resource':resource}),patch.object(sys,'argv',['worker','--model',directory,'--benchmark',str(sample)]),patch.object(worker.subprocess,'Popen') as launch,contextlib.redirect_stdout(output):
                self.assertEqual(worker.main(),0);launch.assert_not_called()
            report=json.loads(output.getvalue());self.assertEqual(report['text'],'one two');self.assertEqual(report['audioSeconds'],0.1);self.assertEqual(report['peakMemoryMiB'],100)

    def test_capture_failure_reports_error_and_cleans_up(self):
        process=Mock();process.poll.return_value=None;process.stdout.fileno.return_value=10;output=io.StringIO();worker.STOP=False
        with patch.object(worker,'tune'),patch.dict(sys.modules,{'vosk':self.fake_vosk()}),patch.object(sys,'argv',['worker','--model','fixture','--source','bluez_source.C0_86_B3_F2_E8_96.headset_head_unit']),patch.object(worker.signal,'signal'),patch.object(worker.subprocess,'Popen',return_value=process),patch.object(worker.select,'select',return_value=([process.stdout],[],[])),patch.object(worker.os,'read',side_effect=[struct.pack('<h',3000)*800,b'']),contextlib.redirect_stdout(output):
            self.assertEqual(worker.main(),1)
        events=[json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual([event['kind'] for event in events],['ready','partial','error'])
        process.terminate.assert_called_once();process.stdout.close.assert_called_once()


if __name__=='__main__':unittest.main()
