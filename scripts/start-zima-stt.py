#!/usr/bin/env python3
"""Restart only this SSD speech server, preserving private pairing and local fallback."""
import argparse
import http.client
import json
import os
from pathlib import Path
import signal
import socket
import ssl
import subprocess
import time


def is_ours(arguments,script,root):
    return str(script) in arguments and '--root' in arguments and arguments[arguments.index('--root')+1:arguments.index('--root')+2]==[str(root)]


def health(root):
    config=json.loads((root/'zima-stt.json').read_text())
    context=ssl.create_default_context(cadata=config['certificate'])
    connection=http.client.HTTPSConnection('127.0.0.1',8766,context=context,timeout=2)
    try:
        connection.request('POST','/health',b'',{'Authorization':'Bearer '+config['token']})
        response=connection.getresponse()
        if response.status!=200:raise ValueError('Server health rejected.')
        return json.loads(response.read(2000))
    finally:connection.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cloud',action='store_true',help='Enable paid OpenAI requests explicitly.')
    parser.add_argument('--stop',action='store_true')
    args=parser.parse_args()
    root=Path('/mnt/camera-ssd/SmartKeyboard-STT')
    script=Path(__file__).resolve().parent.parent/'backend/zima_stt_server.py'
    if os.geteuid()==0:parser.error('Run as casaos, without sudo.')
    if args.cloud and not (root/'openai-api-key').is_file():parser.error('Private API key is missing.')
    pidfile=root/'server.pid'
    if pidfile.exists():
        pid=int(pidfile.read_text().strip());process_path=Path('/proc')/str(pid)
        if process_path.exists():
            command=(process_path/'cmdline').read_bytes().decode().strip('\0').split('\0')
            if not is_ours(command,script,root):parser.error('PID belongs to another process; nothing stopped.')
            os.kill(pid,signal.SIGTERM)
            for unused in range(40):
                if not process_path.exists() or not (process_path/'cmdline').read_bytes():break
                time.sleep(0.1)
            else:parser.error('Previous server did not exit; no second server started.')
    if args.stop:
        print('Speech server stopped. Other services and private files unchanged.');return
    with socket.socket() as probe:
        probe.settimeout(1)
        if probe.connect_ex(('127.0.0.1',8766))==0:parser.error('Port 8766 is still occupied; no other process was stopped.')
    command=[str(root/'venv/bin/python'),str(script),'--root',str(root)]
    if args.cloud:command.append('--cloud')
    with (root/'server.log').open('ab') as log:
        process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    pidfile.write_text(str(process.pid))
    for unused in range(25):
        if process.poll() is not None:parser.error('Speech server exited; inspect SSD server.log.')
        try:
            result=health(root)
            if result.get('ready'):
                print(json.dumps(result));print('No audio uploaded by this startup check.');return
        except (OSError,ValueError):pass
        time.sleep(0.4)
    parser.error('Startup check timed out; inspect SSD server.log before retrying.')


if __name__=='__main__':main()
