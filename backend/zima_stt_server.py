#!/usr/bin/env python3
"""Explicitly started, TLS-protected LAN English STT; no audio files or HID."""
import argparse
import hmac
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import os
from pathlib import Path
import secrets
import ssl
import subprocess
import threading
import time
import wave

MAX_AUDIO = 16000 * 2 * 60


def private_ip(value):
    address = ipaddress.ip_address(value)
    if address.version != 4 or not address.is_private or address.is_loopback:
        raise ValueError('Use a private IPv4 LAN address.')
    return str(address)


def initialize(root, host, client):
    host, client = private_ip(host), private_ip(client)
    root.mkdir(parents=True, exist_ok=True)
    config = root / 'zima-stt.json'
    if any((root / name).exists() for name in ('server.key', 'server.crt', 'zima-stt.json')):
        raise ValueError('Existing pairing/certificate files preserved. Reuse them; do not initialize again.')
    subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-sha256',
                    '-nodes', '-days', '365', '-keyout', str(root / 'server.key'),
                    '-out', str(root / 'server.crt'), '-subj', '/CN=SmartKeyboard Zima STT',
                    '-addext', 'subjectAltName=IP:' + host + ',IP:127.0.0.1'],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.chmod(root / 'server.key', 0o600)
    config.write_text(json.dumps({'version': 1, 'enabled': True, 'host': host,
        'port': 8766, 'client': client, 'token': secrets.token_hex(32),
        'certificate': (root / 'server.crt').read_text()}, indent=2))
    os.chmod(config, 0o600)
    print('Pairing file:', config, flush=True)
    print('Copy ONLY zima-stt.json to Radxa ~/SmartKeyboard/config/zima-stt.json; keep it private.', flush=True)


def load_config(root):
    config = json.loads((root / 'zima-stt.json').read_text())
    private_ip(config['host']); private_ip(config['client'])
    if config.get('version') != 1 or config.get('port') != 8766 or len(config.get('token', '')) != 64:
        raise ValueError('Invalid pairing file.')
    return config


def recognize(model, pcm):
    from vosk import KaldiRecognizer
    recognizer = KaldiRecognizer(model, 16000)
    parts = []
    started = time.monotonic()
    for offset in range(0, len(pcm), 8000):
        if recognizer.AcceptWaveform(pcm[offset:offset + 8000]):
            parts.append(json.loads(recognizer.Result()).get('text', ''))
    parts.append(json.loads(recognizer.FinalResult()).get('text', ''))
    return {'text': ' '.join(filter(None, parts))[:4000],
            'recognitionSeconds': round(time.monotonic() - started, 3)}


def handler_for(config, transcribe):
    busy = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Never log tokens, audio, recognized text, or HTTP headers.

        def setup(self):
            super().setup()
            self.connection.settimeout(30)

        def reply(self, code, payload):
            data = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Connection', 'close')
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            if self.client_address[0] not in (config['client'], '127.0.0.1'):
                self.reply(403, {'error': 'Client not allowed.'}); return
            if not hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + config['token']):
                self.reply(401, {'error': 'Pairing required.'}); return
            if self.headers.get('Transfer-Encoding'):
                self.reply(400, {'error': 'Fixed content length required.'}); return
            try:
                length = int(self.headers.get('Content-Length', '-1'))
            except ValueError:
                length = -1
            if self.path == '/health' and length == 0:
                self.reply(200, {'ready': True, 'engine': 'ZimaBoard local English'}); return
            if self.path != '/transcribe':
                self.reply(404, {'error': 'Unknown endpoint.'}); return
            if length <= 0 or length > MAX_AUDIO or length % 2:
                self.reply(400, {'error': 'Expected up to 60 seconds of mono 16kHz signed 16-bit PCM.'}); return
            if self.headers.get('Content-Type') != 'application/octet-stream':
                self.reply(415, {'error': 'Raw PCM required.'}); return
            if not busy.acquire(blocking=False):
                self.reply(503, {'error': 'Recognizer busy; no automatic retry.'}); return
            try:
                pcm = self.rfile.read(length)
                if len(pcm) != length:
                    self.reply(400, {'error': 'Incomplete recording.'}); return
                result = transcribe(pcm)
                self.reply(200, result)
            except (OSError, ValueError, RuntimeError):
                try:
                    self.reply(500, {'error': 'Recognition failed; draft unchanged.'})
                except OSError:
                    pass
            finally:
                busy.release()
    return Handler


def check(root, sample):
    config = load_config(root)
    context = ssl.create_default_context(cadata=config['certificate'])
    with wave.open(str(sample), 'rb') as wav:
        if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getcomptype()) != (1, 2, 16000, 'NONE'):
            raise ValueError('Self-test needs mono 16-bit 16kHz PCM WAV.')
        if wav.getnframes() * 2 > MAX_AUDIO:
            raise ValueError('Self-test exceeds 60 seconds.')
        pcm = wav.readframes(wav.getnframes())
    connection = http.client.HTTPSConnection('127.0.0.1', config['port'], context=context, timeout=90)
    try:
        connection.request('POST', '/transcribe', pcm, {'Authorization': 'Bearer ' + config['token'], 'Content-Type': 'application/octet-stream'})
        response = connection.getresponse()
        result = json.loads(response.read(20000))
        if response.status != 200:
            raise ValueError(result.get('error', 'Self-test failed.'))
        print(json.dumps(dict(result, tlsVerified=True, audioSeconds=len(pcm) / 32000), indent=2))
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--init', action='store_true')
    parser.add_argument('--host', default='192.168.0.16')
    parser.add_argument('--client', default='192.168.0.17')
    parser.add_argument('--check', type=Path)
    args = parser.parse_args()
    if args.init:
        initialize(args.root, args.host, args.client); return
    if args.check:
        check(args.root, args.check); return
    config = load_config(args.root)
    # Keep recognition to one low-priority core, matching the successful benchmark.
    from local_dictation_worker import tune
    tune()
    from vosk import Model, SetLogLevel
    SetLogLevel(-1)
    model = Model(str(args.root / 'models/vosk-model-small-en-us-0.15'))
    server = ThreadingHTTPServer(('0.0.0.0', config['port']), handler_for(config, lambda pcm: recognize(model, pcm)))
    server.daemon_threads = True
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(args.root / 'server.crt', args.root / 'server.key')
    server.socket = context.wrap_socket(server.socket, server_side=True)
    print('Zima STT ready on TLS port 8766; only configured Radxa and loopback accepted. No audio saved.', flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
