"""Rate-limited background API reachability check. Never uploads audio."""
import http.client
from pathlib import Path
import ssl
import threading
import time


def probe_direct(root):
    key=(Path(root)/'config/openai-api-key').read_text().strip()
    if not key.startswith('sk-') or any(c.isspace() for c in key):
        return {'state':'offline','message':'Cloud key is missing or invalid.'}
    connection=http.client.HTTPSConnection('api.openai.com',context=ssl.create_default_context(),timeout=4)
    try:
        connection.request('GET','/v1/models/gpt-transcribe',headers={'Authorization':'Bearer '+key})
        response=connection.getresponse();response.read(20000)
        if response.status==200:
            return {'state':'online','message':'OpenAI reachable; key and model access accepted. Transcription checks billing.'}
        return {'state':'offline','message':'Cloud check: HTTP '+str(response.status)+'. Check API access/billing.'}
    finally:connection.close()


class CloudHealth:
    def __init__(self,app,route):
        self.app=app;self.route=route;self.lock=threading.Lock();self.busy=False
        self.checked_route=None;self.next_check=0
        self.state={'state':'checking','message':'Cloud status not checked yet.'}

    def snapshot(self):
        route=self.route()
        if route is None:return {'state':'offline','message':'Cloud is disabled or its private configuration is missing.'}
        if route!='direct':return {'state':'unknown','message':'ZimaBoard route configured; OpenAI reachability is not verified here. Direct route supports the live API check.'}
        with self.lock:
            if route!=self.checked_route or time.monotonic()>=self.next_check:
                if not self.busy:
                    self.busy=True;self.checked_route=route;self.next_check=time.monotonic()+60
                    self.state={'state':'checking','message':'Checking OpenAI; no audio upload.'}
                    threading.Thread(target=self._check,daemon=True).start()
            return dict(self.state)

    def _check(self):
        try:result=probe_direct(self.app)
        except (OSError,ValueError,TypeError,http.client.HTTPException):
            result={'state':'offline','message':'Cloud unreachable. Check internet access, certificate/time, or private key.'}
        with self.lock:self.state=result;self.busy=False
