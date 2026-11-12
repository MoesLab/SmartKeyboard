#!/usr/bin/python3
"""Capture real Chromium page errors/layout without reading saved profiles.

Only the new temporary diagnostic browser is stopped when this finishes.
Uses Python's standard library and loopback DevTools; no extra packages.
"""
import argparse
import base64
import hashlib
import json
import os
import shutil
import socket
import struct
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen

class DevTools:
    def __init__(self,url):
        parsed=urlsplit(url);self.sock=socket.create_connection((parsed.hostname,parsed.port),timeout=15)
        self.sock.settimeout(15);self.serial=0
        key=base64.b64encode(os.urandom(16)).decode()
        request=('GET '+parsed.path+' HTTP/1.1\r\nHost: '+parsed.netloc+
                 '\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: '+key+'\r\n\r\n')
        self.sock.sendall(request.encode());headers=b''
        while not headers.endswith(b'\r\n\r\n'):
            headers+=self.read(1)
            if len(headers)>16384:raise RuntimeError('DevTools headers too large')
        expected=base64.b64encode(hashlib.sha1((key+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest())
        if b' 101 ' not in headers.split(b'\r\n')[0] or expected.lower() not in headers.lower():
            raise RuntimeError('DevTools WebSocket handshake rejected')

    def read(self,length):
        result=b''
        while len(result)<length:
            chunk=self.sock.recv(length-len(result))
            if not chunk:raise RuntimeError('DevTools connection closed')
            result+=chunk
        return result

    def send(self,payload,opcode=1):
        mask=os.urandom(4);length=len(payload)
        header=bytes([0x80|opcode,0x80|length]) if length<126 else bytes([0x80|opcode,0xfe])+struct.pack('!H',length) if length<65536 else bytes([0x80|opcode,0xff])+struct.pack('!Q',length)
        self.sock.sendall(header+mask+bytes(value^mask[i%4] for i,value in enumerate(payload)))

    def receive(self):
        payload=b''
        while True:
            first,second=self.read(2);length=second&0x7f
            if length==126:length=struct.unpack('!H',self.read(2))[0]
            if length==127:length=struct.unpack('!Q',self.read(8))[0]
            if length>20_000_000:raise RuntimeError('DevTools response too large')
            mask=self.read(4) if second&0x80 else None
            part=self.read(length)
            if mask:part=bytes(v^mask[i%4] for i,v in enumerate(part))
            opcode=first&0x0f
            if opcode==8:raise RuntimeError('DevTools socket closed')
            if opcode==9:self.send(part,10);continue
            if opcode==10:continue
            payload+=part
            if first&0x80:return json.loads(payload)

    def call(self,method,params=None):
        self.serial+=1;identifier=self.serial
        self.send(json.dumps({'id':identifier,'method':method,'params':params or {}}).encode())
        while True:
            message=self.receive()
            if message.get('id')==identifier:
                if 'error' in message:raise RuntimeError(str(message['error']))
                return message.get('result',{})

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--app-home',default=str(Path.home()/'SmartKeyboard'))
    parser.add_argument('--browser');parser.add_argument('--headless',action='store_true')
    args=parser.parse_args();home=Path(args.app_home).resolve();logdir=home/'logs';logdir.mkdir(exist_ok=True)
    browser=args.browser or shutil.which('chromium') or shutil.which('chromium-browser')
    if not browser:raise SystemExit('Chromium executable not found')
    entry=home/'src'/'index.html'
    if not entry.is_file():raise SystemExit('Missing '+str(entry))
    profile=Path(tempfile.mkdtemp(prefix='smartkeyboard-diagnostic-'))
    command=[browser,'--user-data-dir='+str(profile),'--no-first-run','--disable-gpu','--remote-debugging-port=0','--kiosk']
    if args.headless:command.append('--headless=new')
    command.append(entry.as_uri())
    environment=os.environ.copy();environment['DISPLAY']=':0';environment['XAUTHORITY']=str(Path.home()/'.Xauthority')
    with (logdir/'gui-diagnostic-browser.log').open('w') as logfile:
        process=subprocess.Popen(command,env=environment,stdout=logfile,stderr=subprocess.STDOUT)
        debugger=None
        try:
            portfile=profile/'DevToolsActivePort'
            deadline=time.monotonic()+25
            while not portfile.exists():
                if process.poll() is not None:raise RuntimeError('Diagnostic browser exited. See logs/gui-diagnostic-browser.log')
                if time.monotonic()>deadline:raise RuntimeError('DevTools did not start. See logs/gui-diagnostic-browser.log')
                time.sleep(.25)
            port=int(portfile.read_text().splitlines()[0]);pages=[]
            while time.monotonic()<deadline:
                with urlopen('http://127.0.0.1:'+str(port)+'/json/list',timeout=5) as response:pages=json.load(response)
                pages=[page for page in pages if page.get('type')=='page']
                if pages:break
                time.sleep(.2)
            if not pages:raise RuntimeError('No page target created')
            debugger=DevTools(pages[0]['webSocketDebuggerUrl'])
            debugger.call('Runtime.enable');debugger.call('Page.enable')
            debugger.call('Page.bringToFront')
            debugger.call('Page.addScriptToEvaluateOnNewDocument',{'source':"window.__guiErrors=[];addEventListener('error',e=>__guiErrors.push({message:e.message,file:e.filename,line:e.lineno}));addEventListener('unhandledrejection',e=>__guiErrors.push({message:String(e.reason)}));"})
            debugger.call('Page.reload',{'ignoreCache':True});time.sleep(4)
            expression="""JSON.stringify((()=>{
              const root=document.querySelector('main');const r=root?.getBoundingClientRect();
              const style=root?getComputedStyle(root):null;
              return {url:location.href,title:document.title,ready:document.readyState,
                viewport:[innerWidth,innerHeight],visibility:document.visibilityState,
                main:r?{x:r.x,y:r.y,width:r.width,height:r.height,transform:style.transform,display:style.display,visibility:style.visibility}:null,
                counts:{pages:document.querySelectorAll('#workspaces button').length,phrases:document.querySelectorAll('#quick-buttons button').length,macros:document.querySelectorAll('#macros button').length},
                errors:window.__guiErrors||[],bluetoothConfigPresent:!!window.SMARTKEYBOARD_BRIDGE,
                bluetoothButton:document.querySelector('#bluetooth-open')?.textContent};
            })())"""
            result=debugger.call('Runtime.evaluate',{'expression':expression,'returnByValue':True})
            if 'exceptionDetails' in result:raise RuntimeError(str(result['exceptionDetails']))
            report=json.loads(result['result']['value'])
            report['targetDisplay']=environment['DISPLAY']
            (logdir/'gui-diagnostic.json').write_text(json.dumps(report,indent=2))
            screenshot=debugger.call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':False})
            (logdir/'gui-diagnostic.png').write_bytes(base64.b64decode(screenshot['data']))
            print(json.dumps(report,indent=2))
            print('Screenshot:',logdir/'gui-diagnostic.png')
        finally:
            if debugger:debugger.sock.close()
            process.terminate()
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:print('Diagnostic browser did not close; no other processes were touched.')

if __name__=='__main__':main()
