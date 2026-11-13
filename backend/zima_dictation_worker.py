#!/usr/bin/env python3
"""Capture on Radxa; explicitly send bounded RAM-only audio to paired LAN STT."""
import argparse
import http.client
import ipaddress
import json
import os
from pathlib import Path
import select
import signal
import ssl
import subprocess
import time

STOP = False
MAX_AUDIO = 16000 * 2 * 60


def load_pairing(path):
    data = json.loads(Path(path).read_text())
    address = ipaddress.ip_address(data['host'])
    if address.version != 4 or not address.is_private or address.is_loopback or address.is_link_local:
        raise ValueError('Zima STT requires a private IPv4 LAN address.')
    if data.get('version') != 1 or data.get('enabled') is not True or data.get('port') != 8766:
        raise ValueError('Zima STT is disabled or its pairing file is invalid.')
    token = data.get('token', '')
    if not isinstance(token, str) or len(token) != 64 or any(c not in '0123456789abcdef' for c in token):
        raise ValueError('Invalid Zima STT pairing token.')
    ssl.create_default_context(cadata=data['certificate'])
    return data


def request(data, path, body=b'', timeout=90):
    context = ssl.create_default_context(cadata=data['certificate'])
    connection = http.client.HTTPSConnection(data['host'], data['port'], context=context, timeout=timeout)
    try:
        connection.request('POST', path, body, {'Authorization': 'Bearer ' + data['token'], 'Content-Type': 'application/octet-stream'})
        response = connection.getresponse()
        payload = response.read(20001)
        if len(payload) > 20000:
            raise ValueError('Unexpected recognition response.')
        result = json.loads(payload)
        if response.status != 200:
            raise ValueError(result.get('error', 'Zima STT request failed.'))
        return result
    finally:
        connection.close()


def emit(kind, **data):
    print(json.dumps(dict(kind=kind, **data)), flush=True)


def stop(*unused):
    global STOP
    STOP = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--source')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    process = None
    stage = 'pairing'
    try:
        data = load_pairing(args.config)
        if args.check:
            print(json.dumps(request(data, '/health', timeout=5))); return 0
        signal.signal(signal.SIGINT, stop); signal.signal(signal.SIGTERM, stop)
        stage = 'connection'
        request(data, '/health', timeout=3)
        if STOP:
            emit('done', message='Stopped before capture.'); return 0
        if args.source != 'bluez_source.C0_86_B3_F2_E8_96.headset_head_unit':
            raise ValueError('Select the confirmed OpenComm2 microphone.')
        stage = 'microphone'
        from headset_audio import measure_pcm
        process = subprocess.Popen(['parec', '--device=' + args.source, '--raw', '--format=s16le', '--rate=16000', '--channels=1'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        emit('ready', message='Listening on Radxa · Stop to transcribe on ZimaBoard')
        recording = bytearray(); pending = b''; deadline = time.monotonic() + 60
        while not STOP and time.monotonic() < deadline and len(recording) < MAX_AUDIO:
            readable, _, _ = select.select([process.stdout], [], [], 0.25)
            if not readable:
                if process.poll() is not None:
                    if STOP: break
                    raise ValueError('Microphone capture ended.')
                continue
            chunk = os.read(process.stdout.fileno(), 6400)
            if not chunk:
                if STOP: break
                raise ValueError('Microphone capture ended. Check the headset.')
            pending += chunk
            length = min(len(pending) // 2 * 2, MAX_AUDIO - len(recording))
            pcm, pending = pending[:length], pending[length:]
            if pcm:
                recording.extend(pcm)
                level, db = measure_pcm(pcm)
                emit('partial', text='', level=level, db=db)
        process.terminate(); process.wait(timeout=2); process.stdout.close(); process = None
        if recording:
            emit('processing', message='Transcribing on your ZimaBoard · please wait', level=0)
            stage = 'transcription'
            result = request(data, '/transcribe', bytes(recording))
            text = result.get('text')
            if not isinstance(text, str) or len(text) > 4000:
                raise ValueError('Invalid recognition result.')
            emit('final', text=text)
        emit('done', message='ZimaBoard transcription ready. Review before inserting.')
        return 0
    except Exception:
        # No private configuration, URL credentials, or audio in error messages.
        emit('error', message='Dictation failed at '+stage+'. Check '+{'pairing':'the private pairing file','connection':'the ZimaBoard server and LAN connection','microphone':'the Shokz microphone in Audio settings','transcription':'the ZimaBoard server log'}[stage]+'. Draft unchanged.')
        return 1
    finally:
        if process is not None:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait(timeout=1)
            process.stdout.close()


if __name__ == '__main__':
    raise SystemExit(main())
