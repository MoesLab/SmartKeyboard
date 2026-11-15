"""Supervise a separate, unprivileged English recognizer; never send HID text."""
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import threading
import time
from zima_dictation_worker import load_pairing
from cloud_health import CloudHealth
from audio_preferences import selected, HEADSET, verify_headset_driver


class LocalDictation:
    def __init__(self,app_home,audio):
        self.app=Path(app_home);self.audio=audio;self.lock=threading.Lock();self.process=None;self.deadline=0
        self.cloud_health=CloudHealth(self.app,self.cloud_route)
        self.state={'id':'','state':'idle','text':'','partial':'','level':0,'message':'Local English dictation is idle.'}

    def cloud_route(self):
        try:
            config=json.loads((self.app/'config/cloud-stt.json').read_text())
            if config.get('enabled') is not True:return None
            route=config.get('route','zima')
            if route=='direct':return 'direct' if (self.app/'config/openai-api-key').is_file() else None
            if route=='zima':
                load_pairing(self.app/'config/zima-stt.json');return 'zima'
        except (OSError,ValueError,TypeError,KeyError,AttributeError):pass
        return None

    def cloud_enabled(self):
        return self.cloud_route() is not None

    def availability(self):
        pairing=self.app/'config/zima-stt.json'
        if pairing.exists():
            try:
                load_pairing(pairing)
                return {'localAvailable':True,'cloudAvailable':self.cloud_enabled(),'language':'en-US','engine':'zima',
                        'setupMessage':'Local-network English recognition on your paired ZimaBoard.'}
            except (OSError,ValueError,KeyError,TypeError):
                return {'localAvailable':False,'cloudAvailable':self.cloud_enabled(),'language':'en-US','engine':'zima',
                        'setupMessage':'ZimaBoard pairing is disabled or invalid. Draft and keyboard are unchanged.'}
        python=self.app/'.venv-stt/bin/python';model=self.app/'models/vosk-model-small-en-us-0.15'
        ready=python.is_file() and (model/'am/final.mdl').is_file()
        message='Install the local English model and run its Radxa benchmark first.'
        try:
            setup=json.loads((self.app/'config/local-stt.json').read_text())
            ready=ready and isinstance(setup,dict) and setup.get('version')==1 and setup.get('enabled') is True
            if isinstance(setup,dict) and setup.get('enabled') is False:
                message='Local English is installed but disabled after its benchmark. Review the speed report before opting in with --allow-slow.'
        except (OSError,ValueError):ready=False
        return {'localAvailable':ready,'cloudAvailable':self.cloud_enabled(),'language':'en-US',
                'setupMessage':message}

    def snapshot(self,keepalive=True):
        with self.lock:
            if keepalive and self.process is not None and self.state['state'] in ('loading','listening','processing'):self.deadline=time.monotonic()+5
            return dict(self.state,cloudRoute=self.cloud_route() or 'disabled',**self.availability())

    def start(self,data):
        mode=data.get('mode','local')
        if mode not in ('local','cloud'):raise ValueError('Unknown dictation mode.')
        if mode=='cloud' and not self.availability().get('cloudAvailable'):raise ValueError('Cloud dictation is not configured. No audio was uploaded.')
        if mode=='local' and not self.availability()['localAvailable']:raise ValueError('Local English model is not installed. Run install-local-stt.py first.')
        memory=Path('/proc/meminfo')
        if memory.exists():
            available=next((int(line.split()[1]) for line in memory.read_text().splitlines() if line.startswith('MemAvailable:')),0)
            if mode=='local' and self.availability().get('engine')!='zima' and available<512*1024:raise ValueError('Local dictation needs more free RAM. Keyboard and draft are unchanged.')
        with self.lock:
            if self.process is not None:raise ValueError('Dictation is already running.')
        source=selected(self.app)
        if source==HEADSET:verify_headset_driver(self.app)
        if not any(d['name']==source for d in self.audio.status()['inputs']):raise ValueError('Selected microphone unavailable. Use Audio settings; no other microphone was substituted.')
        if self.audio.session_prefix is None:raise ValueError('Desktop audio session is unavailable.')
        if getattr(getattr(self.audio,'check',None),'active',False) is True:raise ValueError('Wait for the microphone test to finish.')
        self.audio.stop_meter()
        command=self.audio.session_prefix+[str(self.app/'.venv-stt/bin/python'),str(Path(__file__).with_name('local_dictation_worker.py')),'--model',str(self.app/'models/vosk-model-small-en-us-0.15'),'--source',source]
        remote=self.availability().get('engine')=='zima'
        if remote:
            command=self.audio.session_prefix+['/usr/bin/python3',str(Path(__file__).with_name('zima_dictation_worker.py')),'--config',str(self.app/'config/zima-stt.json'),'--source',source,'--mode',mode]
        direct=mode=='cloud' and self.cloud_route()=='direct'
        if direct:
            command=self.audio.session_prefix+['/usr/bin/python3',str(Path(__file__).with_name('zima_dictation_worker.py')),'--direct-key-dir',str(self.app/'config'),'--source',source,'--mode','cloud']
        process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,encoding='utf-8',bufsize=1,start_new_session=True)
        with self.lock:
            self.process=process;self.deadline=time.monotonic()+5;self.hard_deadline=time.monotonic()+90
            self.state={'id':secrets.token_hex(8),'state':'loading','text':'','partial':'','level':0,'mode':mode,'message':'Preparing direct cloud dictation…' if direct else 'Connecting to ZimaBoard…' if remote else 'Loading local English model…'}
        threading.Thread(target=self._read,args=(process,),daemon=True).start()
        threading.Thread(target=self._watch,args=(process,),daemon=True).start()
        return self.snapshot()

    def stop(self):
        with self.lock:
            process=self.process
            if process is not None:self.state['state']='stopping';self.state['message']='Stopping local dictation…';self.deadline=time.monotonic()+2
        if process is not None:
            try:os.killpg(process.pid,signal.SIGINT)
            except ProcessLookupError:pass
        return self.snapshot(False)

    def _watch(self,process):
        while True:
            with self.lock:
                if self.process is not process:return
                stopping=self.state['state']=='stopping';expired=time.monotonic()>self.deadline or (not stopping and time.monotonic()>self.hard_deadline)
            if expired:
                if not stopping:self.stop()
                else:
                    try:os.killpg(process.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                    return
            time.sleep(0.25)

    def _read(self,process):
        try:
            for line in process.stdout:
                event=json.loads(line)
                with self.lock:
                    if self.process is not process:break
                    kind=event.get('kind')
                    if kind=='ready':self.state.update(state='listening',message=event.get('message','Listening locally · English · Stop to review'))
                    elif kind=='processing':
                        self.state.update(state='processing',message=event.get('message','Transcribing locally…'),level=0)
                        self.deadline=time.monotonic()+5;self.hard_deadline=time.monotonic()+100
                    elif kind=='final':
                        text=event.get('text','').strip()
                        if text:self.state['text']=(self.state['text']+' '+text).strip()[:4000]
                        self.state['partial']=''
                    elif kind=='partial':self.state['partial']=event.get('text','')[:500]
                    elif kind=='done':self.state.update(state='done',partial='',message=event.get('message','Dictation stopped.'))
                    elif kind=='error':self.state.update(state='error',message=event.get('message','Local recognition failed.'))
                    if 'spectrum' in event:
                        values=event['spectrum']
                        if isinstance(values,list) and len(values)==24 and all(type(value) in (int,float) and 0<=value<=100 for value in values):self.state['spectrum']=values
                    if 'level' in event:self.state['level']=max(0,min(100,int(event['level'])))
        except (OSError,ValueError,TypeError):
            with self.lock:self.state.update(state='error',message='Local recognizer output failed. Draft unchanged.')
        finally:
            process.stdout.close()
            try:code=process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                try:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                code=process.wait(timeout=2)
            with self.lock:
                if self.process is process:
                    self.process=None;self.state['level']=0;self.state['spectrum']=[]
                    if self.state['state'] not in ('done','error'):self.state.update(state='done' if code==0 else 'error',message='Dictation stopped. Review available text.' if code==0 else 'Recognizer stopped before completion. Review available text.')

    def close(self):
        with self.lock:process=self.process
        self.stop()
        if process is not None:
            try:process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                try:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
