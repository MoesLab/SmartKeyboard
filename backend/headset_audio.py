"""PulseAudio headset gain only: never changes profiles, routes or services."""
import os
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
        return self.status()
