#!/usr/bin/env python3
"""Local-only Vosk worker. Audio stays in memory; JSON events go to its parent."""
import argparse
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time
import wave

STOP=False


def emit(kind,**values):
    print(json.dumps(dict(kind=kind,**values),ensure_ascii=False),flush=True)


def tune():
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
    if hasattr(os,'nice'):os.nice(10)
    if hasattr(os,'sched_getaffinity'):
        allowed=os.sched_getaffinity(0)
        if allowed:os.sched_setaffinity(0,{max(allowed)})


def stop(*unused):
    global STOP
    STOP=True


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',required=True,type=Path)
    parser.add_argument('--source')
    parser.add_argument('--benchmark',type=Path)
    args=parser.parse_args();process=None
    try:
        tune()
        if not args.benchmark:signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
        # Explicit local path avoids Vosk's optional language/model download.
        from vosk import Model,KaldiRecognizer,SetLogLevel
        SetLogLevel(-1)
        started=time.monotonic();model=Model(str(args.model));load_seconds=time.monotonic()-started
        if args.benchmark:
            parts=[]
            with wave.open(str(args.benchmark),'rb') as wav:
                if wav.getnchannels()!=1 or wav.getsampwidth()!=2 or wav.getcomptype()!='NONE':raise ValueError('Benchmark requires mono 16-bit PCM WAV.')
                audio_seconds=wav.getnframes()/wav.getframerate();recognizer=KaldiRecognizer(model,wav.getframerate())
                started=time.monotonic()
                while True:
                    data=wav.readframes(4000)
                    if not data:break
                    if recognizer.AcceptWaveform(data):parts.append(json.loads(recognizer.Result()).get('text',''))
                parts.append(json.loads(recognizer.FinalResult()).get('text',''))
                elapsed=time.monotonic()-started
            import resource
            emit('benchmark',modelLoadSeconds=round(load_seconds,3),audioSeconds=round(audio_seconds,3),recognitionSeconds=round(elapsed,3),realtimeFactor=round(elapsed/max(audio_seconds,0.01),3),peakMemoryMiB=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,1),text=' '.join(filter(None,parts)),cpuCores=1)
            return 0
        if args.source!='bluez_source.C0_86_B3_F2_E8_96.headset_head_unit':raise ValueError('Select the confirmed OpenComm2 microphone.')
        if STOP:emit('done',message='Stopped before listening.');return 0
        from headset_audio import measure_pcm
        signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
        recognizer=KaldiRecognizer(model,16000)
        process=subprocess.Popen(['parec','--device='+args.source,'--raw','--format=s16le','--rate=16000','--channels=1'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        emit('ready',modelLoadSeconds=round(load_seconds,3));deadline=time.monotonic()+60
        pending=b''
        while not STOP and time.monotonic()<deadline:
            readable,_,_=select.select([process.stdout],[],[],0.25)
            if not readable:
                if process.poll() is not None:raise ValueError('Microphone capture ended.')
                continue
            data=os.read(process.stdout.fileno(),6400)
            if not data:
                if STOP:break
                raise ValueError('Microphone capture ended. Check the headset connection.')
            pending+=data;length=len(pending)//2*2
            if not length:continue
            data=pending[:length];pending=pending[length:]
            level,db=measure_pcm(data)
            if recognizer.AcceptWaveform(data):emit('final',text=json.loads(recognizer.Result()).get('text',''),level=level,db=db)
            else:emit('partial',text=json.loads(recognizer.PartialResult()).get('partial',''),level=level,db=db)
        emit('final',text=json.loads(recognizer.FinalResult()).get('text',''))
        emit('done',message='Stopped. Review the recognized text before inserting it.')
        return 0
    except Exception as error:
        emit('error',message=str(error)[:300]);return 1
    finally:
        if process is not None:
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=1)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=1)
            process.stdout.close()


if __name__=='__main__':raise SystemExit(main())
