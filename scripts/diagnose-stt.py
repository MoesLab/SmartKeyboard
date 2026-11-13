#!/usr/bin/env python3
"""Read-only speech diagnostics; never prints pairing credentials or draft text."""
import json
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError

app=Path.home()/'SmartKeyboard'
report={'pairingFilePresent':(app/'config/zima-stt.json').is_file(),
        'installedZimaWorker':Path('/opt/smartkeyboard-bluetooth/zima_dictation_worker.py').is_file()}
try:
    config=json.loads((app/'src/bridge-config.js').read_text().split('=',1)[1].strip().rstrip(';'))
    address=urlparse(config['url'])
    if address.scheme!='http' or address.hostname!='127.0.0.1' or address.port!=8765:
        raise ValueError('Unexpected bridge address')
    request=Request(config['url'].rstrip('/')+'/api/dictation-status',data=b'{}',
                    headers={'Content-Type':'application/json','Origin':'null','Authorization':'Bearer '+config['token']},method='POST')
    try:
        with urlopen(request,timeout=10) as response:state=json.load(response)
        report['dictation']={key:state.get(key) for key in ('state','localAvailable','engine','setupMessage')}
    except HTTPError as error:
        report['bridgeHTTPStatus']=error.code
        try:report['bridgeError']=json.loads(error.read(2000)).get('error','Request failed')
        except (ValueError,TypeError):report['bridgeError']='Request failed'
except Exception as error:report['diagnosticError']=type(error).__name__+'; cannot read local dictation status'
print(json.dumps(report,indent=2))
