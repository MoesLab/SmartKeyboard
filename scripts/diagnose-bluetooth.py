#!/usr/bin/env python3
"""Read this project's bridge status without displaying its authentication token."""
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urlparse
from urllib.request import Request,urlopen


def main():
    output={}
    config_path=Path.home()/'SmartKeyboard/src/bridge-config.js'
    try:
        config=json.loads(config_path.read_text().split('=',1)[1].strip().rstrip(';'))
        parsed=urlparse(config['url'])
        if parsed.scheme!='http' or parsed.hostname!='127.0.0.1' or parsed.port!=8765:
            raise ValueError('Unexpected local bridge address')
        request=Request(config['url'].rstrip('/')+'/api/status',data=b'{}',
                        headers={'Content-Type':'application/json','Origin':'null','Authorization':'Bearer '+config['token']},method='POST')
        with urlopen(request,timeout=10) as response:state=json.load(response)
        output['keyboard']={key:state.get(key) for key in ('registered','ready','host','connectedHosts','connection','queuedReports','error')}
    except Exception as error:output['bridgeError']=type(error).__name__+': unable to read local keyboard status'
    installed=Path('/opt/smartkeyboard-bluetooth/bluetooth_keyboard.py')
    try:output['installedFileHasAudioAccessoryFilter']='def audio_accessory(' in installed.read_text()
    except OSError:output['installedFileHasAudioAccessoryFilter']=None
    for name,address in [('pc','08:5B:D6:F7:82:AC'),('headset','C0:86:B3:F2:E8:96')]:
        try:
            result=subprocess.run(['bluetoothctl','info',address],capture_output=True,text=True,timeout=8,check=True)
            output[name]={key:match.group(1).strip() for key in ('Name','Class','Paired','Trusted','Connected')
                          if (match:=re.search(r'^\s*'+key+r':\s*(.*)$',result.stdout,re.M))}
        except Exception:output[name]={'error':'Unable to read device status'}
    print(json.dumps(output,indent=2))


if __name__=='__main__':main()
