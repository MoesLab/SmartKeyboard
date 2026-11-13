"""PulseAudio headset gain only: never changes profiles, routes or services."""
import os
import io
import json
import tempfile
import math
import select
import signal
import struct
import threading
import time
import wave
from pathlib import Path
import re
import shutil
import subprocess


def parse_devices(output, kind):
    devices=[]
    for block in re.split(r'(?m)^(?:Sink|Source) #\d+\s*$', output)[1:]:
        def field(name):
            found=re.search(r'^\s*'+name+r':\s*(.*?)\s*$',block,re.M)
            return found.group(1) if found else ''
        name=field('Name')
        prefix='bluez_sink.' if kind=='output' else 'bluez_source.'
        if not name.startswith(prefix) or name.endswith('.monitor'):continue
        percentages=re.findall(r'(\d+)%',field('Volume'))
        if not percentages:continue
        devices.append({'name':name,'description':field('Description') or name,
                        'volume':max(map(int,percentages)),'muted':field('Mute')=='yes'})
    return devices


class HeadsetAudio:
    def __init__(self,app_home,runner=None):
        self.startup_config=Path(app_home)/'config/headset-startup.json' if app_home else None
        self.session_prefix=None;self.meter_lock=threading.Lock();self.meter_process=None
        self.meter_deadline=0;self.meter_level=0;self.meter_db=-60;self.meter_message='Microphone level check stopped.'
        if runner is not None:
            self.run=runner
            return
        import pwd
        account=pwd.getpwuid(Path(app_home).stat().st_uid)
        if account.pw_uid==0:raise ValueError('Headset audio requires the desktop user account.')
        pactl=shutil.which('pactl')
        if not pactl:raise ValueError('PulseAudio controls are not installed.')
        env=['/usr/bin/env','LC_ALL=C','XDG_RUNTIME_DIR=/run/user/'+str(account.pw_uid),
             'PULSE_SERVER=unix:/run/user/'+str(account.pw_uid)+'/pulse/native']
        if os.geteuid()==account.pw_uid:prefix=env+[pactl]
        elif os.geteuid()==0:
            runuser=shutil.which('runuser')
            if not runuser:raise ValueError('Desktop audio account helper is unavailable.')
            prefix=[runuser,'-u',account.pw_name,'--']+env+[pactl]
        else:raise ValueError('Cannot access the desktop audio account.')
        self.session_prefix=prefix[:-1]
        def run(arguments):
            try:
                result=subprocess.run(prefix+list(arguments),capture_output=True,text=True,
                                      encoding='utf-8',errors='replace',timeout=1,check=True)
                return result.stdout
            except subprocess.TimeoutExpired:raise ValueError('Headset audio controls timed out.')
            except subprocess.CalledProcessError:raise ValueError('Cannot reach the desktop PulseAudio session. Refresh after reconnecting the headset.')
        self.run=run

    def status(self):
        return {'outputs':[d for d in parse_devices(self.run(['list','sinks']),'output') if d['name'].startswith('bluez_sink.C0_86_B3_F2_E8_96.')],
                'inputs':[d for d in parse_devices(self.run(['list','sources']),'input') if d['name'].startswith('bluez_source.C0_86_B3_F2_E8_96.')]}

    def set_volume(self,data):
        kind=data.get('kind');name=data.get('name');volume=data.get('volume')
        if kind not in ('output','input') or type(volume) is not int or not 0<=volume<=100:
            raise ValueError('Choose a headset level from 0 to 100%.')
        if not isinstance(name,str):raise ValueError('Choose a connected headset.')
        available=self.status()['outputs' if kind=='output' else 'inputs']
        if not any(device['name']==name for device in available):
            raise ValueError('The selected headset endpoint is unavailable. Refresh audio controls.')
        self.run(['set-sink-volume' if kind=='output' else 'set-source-volume',name,str(volume)+'%'])
        result=self.status()
        try:self.save_startup_gain(kind,volume)
        except (OSError,ValueError,KeyError,TypeError):result['warning']='Level changed, but startup saving failed. Keep the current session and check headset-startup.json.'
        return result

    def save_startup_gain(self,kind,volume):
        path=self.startup_config
        if path is None or not path.exists():return
        if path.is_symlink() or path.parent.is_symlink() or path.stat().st_size>10000:raise ValueError('Unexpected startup configuration.')
        settings=json.loads(path.read_text())
        if not isinstance(settings,dict) or settings.get('version')!=1 or settings.get('address')!='C0:86:B3:F2:E8:96' or settings.get('profile')!='headset_head_unit':raise ValueError('Unrecognized headset startup configuration.')
        if kind not in settings or not isinstance(settings[kind],dict):raise ValueError('Missing saved headset level.')
        settings[kind]['volume']=volume
        owner=path.stat();fd,temporary=tempfile.mkstemp(prefix='.headset-level-',dir=str(path.parent))
        try:
            with os.fdopen(fd,'w') as stream:
                json.dump(settings,stream,indent=2);stream.flush();os.fsync(stream.fileno())
                if hasattr(os,'fchown'):os.fchown(stream.fileno(),owner.st_uid,owner.st_gid)
            os.replace(temporary,str(path))
        finally:
            if os.path.exists(temporary):os.unlink(temporary)



    def play_test(self,data):
        name=data.get('name')
        if not any(device['name']==name for device in self.status()['outputs']):
            raise ValueError('Connect OpenComm2 and refresh before testing sound.')
        executable=shutil.which('paplay')
        if not executable or self.session_prefix is None:raise ValueError('Headset playback helper unavailable.')
        try:
            subprocess.run(self.session_prefix+[executable,'--device='+name],input=make_test_tone(),
                           stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=3,check=True)
        except (subprocess.SubprocessError,OSError):raise ValueError('Headset test playback failed. Check the connection and listening level.')
        return {'ok':True,'message':'Test tone played through OpenComm2 at its current listening level.'}

    def start_meter(self,data):
        name=data.get('name')
        if not any(device['name']==name for device in self.status()['inputs']):
            raise ValueError('No OpenComm2 microphone is available in the current audio mode.')
        executable=shutil.which('parec')
        if not executable or self.session_prefix is None:raise ValueError('Microphone level helper unavailable.')
        self.stop_meter()
        command=self.session_prefix+[executable,'--device='+name,'--raw','--format=s16le','--rate=8000','--channels=1']
        try:process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,start_new_session=True)
        except OSError:raise ValueError('Could not start microphone level check.')
        with self.meter_lock:
            self.meter_process=process;self.meter_deadline=time.monotonic()+5
            self.meter_level=0;self.meter_db=-60;self.meter_message='Speak to check the microphone level. No recording is saved.'
        threading.Thread(target=self._read_meter,args=(process,),daemon=True).start()
        return self.meter_status()

    @staticmethod
    def _terminate_capture(process):
        if process.poll() is None:
            try:os.killpg(process.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            try:process.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                try:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                try:process.wait(timeout=0.5)
                except subprocess.TimeoutExpired:pass

    def stop_meter(self):
        with self.meter_lock:
            process=self.meter_process;self.meter_process=None
            self.meter_level=0;self.meter_db=-60;self.meter_message='Microphone level check stopped.'
        if process is not None:threading.Thread(target=self._terminate_capture,args=(process,),daemon=True).start()
        return {'active':False,'level':0,'db':-60,'message':'Microphone level check stopped.'}

    def meter_status(self):
        with self.meter_lock:
            active=self.meter_process is not None
            if active:self.meter_deadline=time.monotonic()+5
            return {'active':active,'level':self.meter_level,'db':self.meter_db,'message':self.meter_message}

    def _read_meter(self,process):
        message='Microphone level check stopped.';pending=b''
        try:
            while True:
                with self.meter_lock:
                    if self.meter_process is not process:break
                    if time.monotonic()>self.meter_deadline:break
                readable,_,_=select.select([process.stdout],[],[],0.25)
                if not readable:continue
                chunk=os.read(process.stdout.fileno(),1600)
                if not chunk:
                    message='Microphone stream ended. Refresh audio and check the headset connection.';break
                pending+=chunk;length=len(pending)//2*2
                if not length:continue
                level,db=measure_pcm(pending[:length]);pending=pending[length:]
                with self.meter_lock:
                    if self.meter_process is process:self.meter_level=level;self.meter_db=db
        except (OSError,ValueError):message='Microphone stream unavailable. Refresh audio to check the connection.'
        finally:
            self._terminate_capture(process)
            process.stdout.close()
            with self.meter_lock:
                if self.meter_process is process:
                    self.meter_process=None;self.meter_level=0;self.meter_db=-60;self.meter_message=message


def make_test_tone():
    rate=16000;frames=[]
    for i in range(int(rate*0.55)):
        t=i/rate;local=t if t<0.25 else t-0.3
        frequency=660 if t<0.25 else 880
        amplitude=0 if 0.25<=t<0.3 else 0.10*max(0,min(1,local/0.02,(0.25-local)/0.02))
        frames.append(struct.pack('<h',round(32767*amplitude*math.sin(2*math.pi*frequency*t))))
    output=io.BytesIO()
    with wave.open(output,'wb') as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(rate);wav.writeframes(b''.join(frames))
    return output.getvalue()


def measure_pcm(data):
    samples=[sample[0] for sample in struct.iter_unpack('<h',data)]
    if not samples:return 0,-60
    rms=math.sqrt(sum(sample*sample for sample in samples)/len(samples))/32768
    db=max(-60,min(0,20*math.log10(max(rms,0.000001))))
    return round((db+60)/60*100),round(db,1)
