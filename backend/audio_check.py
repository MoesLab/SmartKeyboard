"""Four-second RAM-only microphone record/playback, on a background thread."""
import io
import os
import select
import subprocess
import threading
import time
import wave


class AudioCheck:
    def __init__(self):
        self.lock=threading.Lock();self.active=False;self.pcm=b'';self.message='No test recording.';self.generation=0

    def snapshot(self):
        with self.lock:return {'active':self.active,'available':bool(self.pcm),'message':self.message}

    def start(self,prefix,source,output=None):
        with self.lock:
            if self.active:raise ValueError('Audio test already running.')
            if output and not self.pcm:raise ValueError('Record a microphone test first.')
            self.active=True;self.generation+=1;generation=self.generation;self.message='Playing microphone test…' if output else 'Recording 4 seconds; speak now. No upload.'
            if not output:self.pcm=b''
        threading.Thread(target=self._run,args=(prefix,source,output,generation),daemon=True).start()
        return self.snapshot()

    def _run(self,prefix,source,output,generation):
        process=None
        try:
            if output:
                buffer=io.BytesIO()
                with wave.open(buffer,'wb') as wav:
                    wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(16000);wav.writeframes(self.pcm)
                subprocess.run(prefix+['paplay','--device='+output],input=buffer.getvalue(),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=7,check=True)
                message='Test played. Recording remains in RAM for 60 seconds; no upload.'
            else:
                process=subprocess.Popen(prefix+['parec','--device='+source,'--raw','--format=s16le','--rate=16000','--channels=1'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
                deadline=time.monotonic()+4;pcm=bytearray()
                while time.monotonic()<deadline and len(pcm)<128000:
                    ready,_,_=select.select([process.stdout],[],[],0.25)
                    if ready:
                        chunk=os.read(process.stdout.fileno(),min(6400,128000-len(pcm)))
                        if not chunk:break
                        pcm.extend(chunk)
                if not pcm:raise ValueError('No microphone audio.')
                with self.lock:self.pcm=bytes(pcm[:len(pcm)//2*2])
                message='Recorded in RAM. Choose playback output, then Play recording. No upload.'
            with self.lock:self.message=message
        except (OSError,ValueError,subprocess.SubprocessError):
            with self.lock:self.message='Audio test failed. Check selected devices.';self.pcm=b''
        finally:
            if process is not None:
                if process.poll() is None:
                    process.terminate()
                    try:process.wait(timeout=1)
                    except subprocess.TimeoutExpired:process.kill();process.wait(timeout=1)
                process.stdout.close()
            with self.lock:self.active=False
            timer=threading.Timer(60,self.clear,args=(generation,));timer.daemon=True;timer.start()

    def clear(self,generation=None):
        with self.lock:
            if not self.active and (generation is None or generation==self.generation):self.pcm=b''
