"""Bounded, explicit cloud transcription; no files, redirects, retries or HID."""
import http.client
import io
import json
from pathlib import Path
import secrets
import ssl
import wave


def transcribe(root, pcm):
    if not pcm or len(pcm)>1920000 or len(pcm)%2:
        raise ValueError('Recording must be at most 60 seconds of mono 16kHz PCM.')
    key=(Path(root)/'openai-api-key').read_text().strip()
    if not key.startswith('sk-') or any(c.isspace() for c in key):
        raise ValueError('Cloud API key is not configured correctly.')
    output=io.BytesIO()
    with wave.open(output,'wb') as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(16000);wav.writeframes(pcm)
    boundary='smartkeyboard-'+secrets.token_hex(16)
    body=(f'--{boundary}\r\nContent-Disposition: form-data; name="model"\r\n\r\ngpt-transcribe\r\n'
          f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="dictation.wav"\r\n'
          'Content-Type: audio/wav\r\n\r\n').encode()+output.getvalue()+f'\r\n--{boundary}--\r\n'.encode()
    connection=http.client.HTTPSConnection('api.openai.com',context=ssl.create_default_context(),timeout=60)
    try:
        connection.request('POST','/v1/audio/transcriptions',body,
            {'Authorization':'Bearer '+key,'Content-Type':'multipart/form-data; boundary='+boundary})
        response=connection.getresponse();payload=response.read(100001)
        if response.status!=200:
            raise ValueError('Cloud returned HTTP '+str(response.status)+'. Check API billing/access. No automatic retry.')
        if len(payload)>100000:raise ValueError('Cloud response exceeded its limit.')
        text=json.loads(payload).get('text')
        if not isinstance(text,str) or len(text)>4000:raise ValueError('Unexpected cloud transcript.')
        return {'text':text}
    finally:connection.close()
