#!/usr/bin/python3
"""Smart Keyboard BLE HID peripheral and authenticated loopback-only UI bridge.

Requires the OS python3-dbus and python3-gi packages, no pip dependencies.
BlueZ 5.55 APIs: GattManager1, LEAdvertisingManager1 and AgentManager1.
"""
import argparse
import collections
import hmac
import json
import logging
import os
import secrets
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import dbus
import dbus.exceptions
import dbus.mainloop.glib
import dbus.service
from gi.repository import GLib
from hid_keys import REPORT_MAP, RELEASE, encode_text, encode_shortcuts
from headset_audio import HeadsetAudio

PROPS='org.freedesktop.DBus.Properties'
OM='org.freedesktop.DBus.ObjectManager'
SERVICE='org.bluez.GattService1'
CHAR='org.bluez.GattCharacteristic1'
DESC='org.bluez.GattDescriptor1'
ADV='org.bluez.LEAdvertisement1'
AGENT='org.bluez.Agent1'
ADAPTER='org.bluez.Adapter1'
DEVICE='org.bluez.Device1'
ROOT='/com/moeslab/SmartKeyboard'

def uuid(short): return '0000'+short+'-0000-1000-8000-00805f9b34fb'
def byte_array(value): return dbus.Array([dbus.Byte(b) for b in value],signature='y')

class Rejected(dbus.exceptions.DBusException):
    _dbus_error_name='org.bluez.Error.Rejected'

class NotSupported(dbus.exceptions.DBusException):
    _dbus_error_name='org.bluez.Error.NotSupported'

class Properties(dbus.service.Object):
    def get_path(self): return dbus.ObjectPath(self.path)
    @dbus.service.method(PROPS,in_signature='s',out_signature='a{sv}')
    def GetAll(self,interface):
        return self.properties().get(interface,{})

    @dbus.service.method(PROPS,in_signature='ss',out_signature='v')
    def Get(self,interface,name): return self.GetAll(interface)[name]

    @dbus.service.signal(PROPS,signature='sa{sv}as')
    def PropertiesChanged(self,interface,changed,invalidated): pass

class Descriptor(Properties):
    def __init__(self,bus,characteristic,kind,value):
        self.path=characteristic.path+'/reference'; self.characteristic=characteristic
        self.kind=kind; self.value=value
        super().__init__(bus,self.path)

    def properties(self):
        return {DESC:{'UUID':uuid(self.kind),'Characteristic':dbus.ObjectPath(self.characteristic.path),
                      'Flags':dbus.Array(['read'],signature='s')}}

    @dbus.service.method(DESC,in_signature='a{sv}',out_signature='ay')
    def ReadValue(self,options): return byte_array(self.value[int(options.get('offset',0)):])

class Characteristic(Properties):
    def __init__(self,bus,service,index,kind,flags,value=b'',report_type=None,on_write=None):
        self.path=service.path+'/char'+str(index); self.service=service; self.kind=kind
        self.flags=flags; self.value=value; self.notifying=False; self.on_write=on_write
        super().__init__(bus,self.path)
        self.descriptors=[]
        if report_type is not None:
            self.descriptors.append(Descriptor(bus,self,'2908',bytes([1,report_type])))

    def properties(self):
        return {CHAR:{'UUID':uuid(self.kind),'Service':dbus.ObjectPath(self.service.path),
                      'Flags':dbus.Array(self.flags,signature='s'),'Notifying':dbus.Boolean(self.notifying),
                      'Descriptors':dbus.Array([dbus.ObjectPath(d.path) for d in self.descriptors],signature='o')}}

    @dbus.service.method(CHAR,in_signature='a{sv}',out_signature='ay')
    def ReadValue(self,options):
        if 'read' not in self.flags: raise NotSupported()
        return byte_array(self.value[int(options.get('offset',0)):])

    @dbus.service.method(CHAR,in_signature='aya{sv}',out_signature='')
    def WriteValue(self,value,options):
        if not any(flag in self.flags for flag in ('write','write-without-response')): raise NotSupported()
        if int(options.get('offset',0)): raise NotSupported('Offset writes not supported')
        data=bytes(value)
        if self.on_write: self.on_write(data)
        self.value=data

    @dbus.service.method(CHAR,in_signature='',out_signature='')
    def StartNotify(self):
        if 'notify' not in self.flags: raise NotSupported()
        self.notifying=True
        self.PropertiesChanged(CHAR,{'Notifying':dbus.Boolean(True)},[])

    @dbus.service.method(CHAR,in_signature='',out_signature='')
    def StopNotify(self):
        self.notifying=False
        self.PropertiesChanged(CHAR,{'Notifying':dbus.Boolean(False)},[])

    def emit(self,value):
        self.value=value
        if self.notifying: self.PropertiesChanged(CHAR,{'Value':byte_array(value)},[])

class Service(Properties):
    def __init__(self,bus,index,kind):
        self.path=ROOT+'/service'+str(index); self.kind=kind; self.characteristics=[]
        super().__init__(bus,self.path)

    def properties(self):
        return {SERVICE:{'UUID':uuid(self.kind),'Primary':dbus.Boolean(True),
                         'Characteristics':dbus.Array([dbus.ObjectPath(c.path) for c in self.characteristics],signature='o')}}

    def add(self,bus,kind,flags,value=b'',**kwargs):
        item=Characteristic(bus,self,len(self.characteristics),kind,flags,value,**kwargs)
        self.characteristics.append(item);return item

class Application(dbus.service.Object):
    def __init__(self,bus,controller):
        self.path=ROOT
        super().__init__(bus,ROOT)
        hid=Service(bus,0,'1812')
        hid.add(bus,'2a4a',['read'],bytes([0x11,0x01,0,0x02]))
        hid.add(bus,'2a4b',['read','encrypt-read'],REPORT_MAP)
        controller.input=hid.add(bus,'2a4d',['read','notify','encrypt-read'],RELEASE,report_type=1)
        hid.add(bus,'2a4d',['read','write','write-without-response','encrypt-read','encrypt-write'],b'\0',report_type=2)
        hid.add(bus,'2a4c',['write-without-response'],b'\1',on_write=controller.control_write)
        hid.add(bus,'2a4e',['read','write-without-response'],b'\1',on_write=controller.protocol_write)
        controller.boot_input=hid.add(bus,'2a22',['read','notify','encrypt-read'],RELEASE)
        hid.add(bus,'2a32',['read','write','write-without-response','encrypt-read','encrypt-write'],b'\0')
        info=Service(bus,1,'180a')
        info.add(bus,'2a29',['read'],b'MoesLab')
        info.add(bus,'2a24',['read'],b'Smart Keyboard')
        self.services=[hid,info]

    def get_path(self): return dbus.ObjectPath(self.path)

    @dbus.service.method(OM,out_signature='a{oa{sa{sv}}}')
    def GetManagedObjects(self):
        objects={}
        for service in self.services:
            objects[dbus.ObjectPath(service.path)]=service.properties()
            for characteristic in service.characteristics:
                objects[dbus.ObjectPath(characteristic.path)]=characteristic.properties()
                for descriptor in characteristic.descriptors:
                    objects[dbus.ObjectPath(descriptor.path)]=descriptor.properties()
        return objects

class Advertisement(Properties):
    def __init__(self,bus):
        self.path=ROOT+'/advertisement';super().__init__(bus,self.path)

    def properties(self):
        return {ADV:{'Type':'peripheral','ServiceUUIDs':dbus.Array([uuid('1812')],signature='s'),
                     'LocalName':'Smart Keyboard','Appearance':dbus.UInt16(0x03c1)}}

    @dbus.service.method(ADV,in_signature='',out_signature='')
    def Release(self): logging.info('Advertisement released')

class PairingAgent(dbus.service.Object):
    def __init__(self,bus,controller):
        self.controller=controller;self.pending=None;self.reply=None;self.error=None
        self.path=ROOT+'/agent';super().__init__(bus,self.path)

    def get_path(self): return dbus.ObjectPath(self.path)

    def request(self,device,kind,reply,error,code=None):
        if time.monotonic()>self.controller.pair_until or self.pending:
            error(Rejected('Open pairing on the touchscreen first'));return
        self.pending={'id':secrets.token_hex(8),'device':str(device),'kind':kind,'code':code}
        self.reply=reply;self.error=error
        logging.info('Pairing approval needed: %s',kind)

    @dbus.service.method(AGENT,in_signature='ou',out_signature='',async_callbacks=('reply','error'))
    def RequestConfirmation(self,device,passkey,reply,error):
        self.request(device,'confirm',reply,error,'%06d'%passkey)

    @dbus.service.method(AGENT,in_signature='o',out_signature='u',async_callbacks=('reply','error'))
    def RequestPasskey(self,device,reply,error): self.request(device,'passkey',reply,error)

    @dbus.service.method(AGENT,in_signature='o',out_signature='',async_callbacks=('reply','error'))
    def RequestAuthorization(self,device,reply,error): self.request(device,'authorize',reply,error)

    @dbus.service.method(AGENT,in_signature='o',out_signature='s')
    def RequestPinCode(self,device): raise Rejected('Legacy PIN pairing is not supported')

    @dbus.service.method(AGENT,in_signature='ouq',out_signature='')
    def DisplayPasskey(self,device,passkey,entered):
        if time.monotonic()>self.controller.pair_until: raise Rejected()
        self.controller.pair_display={'code':'%06d'%passkey,'entered':int(entered)}

    @dbus.service.method(AGENT,in_signature='os',out_signature='')
    def DisplayPinCode(self,device,pin): raise Rejected('Legacy PIN pairing not supported')

    @dbus.service.method(AGENT,in_signature='os',out_signature='')
    def AuthorizeService(self,device,service_uuid):
        properties=self.controller.device_properties(str(device))
        if not properties.get('Paired') or service_uuid not in (uuid('1812'),uuid('1124')):
            raise Rejected('Only paired HID clients are authorized')

    @dbus.service.method(AGENT,in_signature='',out_signature='')
    def Cancel(self): self.resolve(False)

    @dbus.service.method(AGENT,in_signature='',out_signature='')
    def Release(self): self.resolve(False)

    def resolve(self,accepted,passkey=None):
        if not self.pending: return
        pending,reply,error=self.pending,self.reply,self.error
        self.pending=None;self.reply=None;self.error=None
        if not accepted: error(Rejected('Declined on the touchscreen'))
        elif pending['kind']=='passkey': reply(dbus.UInt32(passkey))
        else: reply()

class Controller:
    def __init__(self,bus,adapter,report_interval_ms=5):
        self.bus=bus;self.adapter=adapter;self.objects={};self.registered=False
        self.error='Starting';self.pair_until=0;self.pair_display=None;self.old_pairing=None
        self.protocol=1;self.suspended=False;self.queue=collections.deque();self.queue_target=None
        self.shutdown_pending=False;self.shutdown_error=''
        self.delivery={'id':'','state':'idle','totalReports':0,'remainingReports':0,'actionsSent':0,'host':'','message':'No send yet'}
        self.last_message='Bluetooth keyboard starting';self.input=None;self.boot_input=None
        self.props=dbus.Interface(bus.get_object('org.bluez',adapter),PROPS)
        self.agent=PairingAgent(bus,self)
        self.refresh_objects()
        bus.add_signal_receiver(self.changed,bus_name='org.bluez',dbus_interface=PROPS,signal_name='PropertiesChanged',path_keyword='path')
        bus.add_signal_receiver(self.added,bus_name='org.bluez',dbus_interface=OM,signal_name='InterfacesAdded')
        bus.add_signal_receiver(self.removed,bus_name='org.bluez',dbus_interface=OM,signal_name='InterfacesRemoved')
        self.report_interval_ms=report_interval_ms
        self.report_timer=GLib.timeout_add(report_interval_ms,self.tick)
        GLib.timeout_add_seconds(1,self.expire_pairing)

    def refresh_objects(self):
        manager=dbus.Interface(self.bus.get_object('org.bluez','/'),OM)
        self.objects={str(p):dict(v) for p,v in manager.GetManagedObjects().items()}

    def changed(self,interface,values,invalidated,path=None):
        if interface==DEVICE:
            self.objects.setdefault(str(path),{}).setdefault(DEVICE,{}).update(values)
            if values.get('Paired'):
                self.pair_display=None
                self.close_pairing()

    def added(self,path,interfaces): self.objects.setdefault(str(path),{}).update(interfaces)
    def removed(self,path,interfaces):
        for interface in interfaces: self.objects.get(str(path),{}).pop(interface,None)
    def device_properties(self,path): return self.objects.get(path,{}).get(DEVICE,{})

    @staticmethod
    def audio_accessory(properties):
        # Do not use audio UUIDs: Windows PCs can advertise those too.
        try:major=(int(properties.get('Class',0))>>8)&0x1f
        except (ValueError,TypeError):major=0
        if major:return major==4  # Bluetooth Audio/Video major device class.
        return str(properties.get('Icon','')) in ('audio-headset','audio-headphones','audio-speakers')

    def hosts(self):
        return [(p,v[DEVICE]) for p,v in self.objects.items() if p.startswith(self.adapter+'/') and DEVICE in v and v[DEVICE].get('Connected') and v[DEVICE].get('Paired') and not self.audio_accessory(v[DEVICE])]

    def active_report(self): return self.boot_input if self.protocol==0 else self.input

    def ready(self):
        return self.registered and not getattr(self,'shutdown_pending',False) and len(self.hosts())==1 and self.active_report().notifying and not self.suspended

    def connection_status(self):
        if not self.registered:return 'offline'
        if getattr(self,'shutdown_pending',False):return 'shutting-down'
        hosts=self.hosts()
        if not hosts:return 'waiting'
        if len(hosts)>1:return 'multiple'
        if self.suspended:return 'suspended'
        if not self.active_report().notifying:return 'subscribing'
        return 'ready'

    def snapshot(self):
        hosts=self.hosts()
        return {'registered':self.registered,'ready':bool(self.ready()),'error':self.error,
                'host':str(hosts[0][1].get('Alias','Paired PC')) if len(hosts)==1 else '',
                'connectedHosts':len(hosts),'queuedReports':len(self.queue),'connection':self.connection_status(),
                'delivery':dict(getattr(self,'delivery',{})),'reportIntervalMs':getattr(self,'report_interval_ms',5),
                'pairingSeconds':max(0,int(self.pair_until-time.monotonic())),
                'pairing':self.agent.pending,'displayPasskey':self.pair_display,'message':self.last_message,
                'shutdownPending':getattr(self,'shutdown_pending',False),'shutdownError':getattr(self,'shutdown_error','')}

    def protocol_write(self,value):
        if value not in (b'\0',b'\1'): raise NotSupported('Protocol must be boot or report')
        self.protocol=value[0]

    def control_write(self,value):
        if value not in (b'\0',b'\1'): raise NotSupported('Unknown HID control point')
        self.suspended=value==b'\0'

    def enqueue(self,reports,report_interval_ms=None):
        if report_interval_ms is not None and (type(report_interval_ms) is not int or report_interval_ms not in (5,10,15)):
            raise ValueError('Choose 5, 10 or 15 milliseconds per report.')
        if not self.ready():
            raise ValueError('PC keyboard connection is not ready ('+self.connection_status()+'). Draft kept; nothing sent. Open Bluetooth and refresh the connection.')
        if self.queue:raise ValueError('A send is in progress; wait or use Stop send in Bluetooth settings.')
        if report_interval_ms is not None and report_interval_ms!=getattr(self,'report_interval_ms',5):
            timer=GLib.timeout_add(report_interval_ms,self.tick)
            old_timer=getattr(self,'report_timer',None)
            if old_timer is not None:GLib.source_remove(old_timer)
            self.report_timer=timer;self.report_interval_ms=report_interval_ms
        self.queue_target=self.hosts()[0][0];self.queue.extend(reports)
        host=str(self.hosts()[0][1].get('Alias','PC'))
        self.delivery={'id':secrets.token_hex(8),'state':'queued','totalReports':len(reports),'remainingReports':len(reports),'actionsSent':0,'host':host,'message':'Keystrokes queued for '+host}
        self.last_message=self.delivery['message']
        return {'ok':True,'message':self.last_message,'delivery':dict(self.delivery)}

    def stop_delivery(self,message,state='stopped'):
        self.queue.clear()
        for characteristic in (self.input,self.boot_input):
            try:characteristic.emit(RELEASE)
            except Exception:logging.exception('Could not emit key release after send stopped')
        if getattr(self,'delivery',None):
            self.delivery.update(state=state,remainingReports=0,message=message)
        self.last_message=message

    def tick(self):
        if self.queue:
            if not self.ready() or self.hosts()[0][0]!=self.queue_target:
                self.stop_delivery('Send interrupted by Bluetooth change. Draft kept; check the PC before resending.')
            else:
                try:
                    self.active_report().emit(self.queue.popleft())
                    self.delivery['remainingReports']=len(self.queue)
                    self.delivery['actionsSent']=(self.delivery['totalReports']-len(self.queue))//2
                    if self.queue:
                        self.delivery['state']='sending'
                        self.delivery['message']='Sending '+str(self.delivery['actionsSent'])+'/'+str(self.delivery['totalReports']//2)+' key actions to '+self.delivery['host']
                    else:
                        self.delivery['state']='sent'
                        self.delivery['message']='Reports sent to '+self.delivery['host']+'. Check the target PC app.'
                    self.last_message=self.delivery['message']
                except Exception:
                    logging.exception('Bluetooth report emission failed')
                    self.stop_delivery('Send failed during Bluetooth output. Check the PC before resending.','failed')
        return True

    def open_pairing(self):
        if self.queue: raise ValueError('Wait for the current send to finish.')
        if self.old_pairing is None:
            self.old_pairing=(bool(self.props.Get(ADAPTER,'Pairable')),bool(self.props.Get(ADAPTER,'Discoverable')))
        self.props.Set(ADAPTER,'Pairable',dbus.Boolean(True))
        self.props.Set(ADAPTER,'Discoverable',dbus.Boolean(True))
        self.pair_until=time.monotonic()+120
        self.last_message='Pairing open for two minutes; add Smart Keyboard on your PC'
        return {'ok':True}

    def close_pairing(self):
        self.pair_until=0
        if self.old_pairing is not None:
            pairable,discoverable=self.old_pairing;self.old_pairing=None
            try:
                self.props.Set(ADAPTER,'Pairable',dbus.Boolean(pairable))
                self.props.Set(ADAPTER,'Discoverable',dbus.Boolean(discoverable))
            except dbus.exceptions.DBusException: logging.exception('Restoring pairing settings')

    def expire_pairing(self):
        if self.old_pairing is not None and time.monotonic()>self.pair_until:
            self.agent.resolve(False);self.close_pairing();self.pair_display=None
        return True

    def request_shutdown(self,data):
        if data.get('confirm') is not True:
            raise ValueError('Shutdown requires confirmation on the touchscreen.')
        manager=dbus.Interface(self.bus.get_object('org.freedesktop.login1','/org/freedesktop/login1'),
                               'org.freedesktop.login1.Manager')
        if str(manager.CanPowerOff())!='yes':
            raise ValueError('Linux cannot power off without further authorization. Use MobaXterm: sudo systemctl poweroff')
        self.queue.clear();self.input.emit(RELEASE);self.boot_input.emit(RELEASE)
        self.agent.resolve(False);self.close_pairing()
        self.shutdown_pending=True;self.shutdown_error=''
        self.last_message='Orderly shutdown requested; wait until the Radxa finishes powering down.'
        def failed(error):
            self.shutdown_pending=False;self.shutdown_error='Shutdown failed: '+str(error)
            self.last_message=self.shutdown_error
            logging.error(self.shutdown_error)
        def power_off():
            try:
                manager.PowerOff(dbus.Boolean(False),reply_handler=lambda:None,error_handler=failed)
            except Exception as error: failed(error)
            return False
        # Give the HTTP acknowledgement and in-app notice time to render.
        GLib.timeout_add(1500,power_off)
        return {'ok':True,'message':self.last_message}

    def handle(self,route,data):
        if route=='/api/status': return self.snapshot()
        if getattr(self,'shutdown_pending',False): raise ValueError('Shutdown is already in progress.')
        if route=='/api/shutdown': return self.request_shutdown(data)
        if route=='/api/refresh':
            self.refresh_objects();return self.snapshot()
        if route=='/api/cancel-send':
            if self.queue:self.stop_delivery('Send stopped by user. Draft kept; check the PC before resending.','cancelled')
            return {'ok':True,'message':self.last_message,'delivery':dict(getattr(self,'delivery',{}))}
        if route in ('/api/audio-status','/api/audio-volume','/api/audio-test','/api/audio-meter-start','/api/audio-meter-status','/api/audio-meter-stop'):
            if self.queue and route not in ('/api/audio-meter-status','/api/audio-meter-stop'):raise ValueError('Wait for sending to finish before adjusting headset audio.')
            if not hasattr(self,'audio'):
                if not hasattr(self,'audio_home'):raise ValueError('Audio controls unavailable; reinstall the backend.')
                self.audio=HeadsetAudio(self.audio_home)
            if route=='/api/audio-status':return self.audio.status()
            if route=='/api/audio-volume':return self.audio.set_volume(data)
            if route=='/api/audio-test':return self.audio.play_test(data)
            if route=='/api/audio-meter-start':return self.audio.start_meter(data)
            if route=='/api/audio-meter-stop':return self.audio.stop_meter()
            return self.audio.meter_status()
        if route=='/api/pair': return self.open_pairing()
        if route=='/api/send': return self.enqueue(encode_text(data.get('text')),data.get('reportIntervalMs'))
        if route=='/api/macro': return self.enqueue(encode_shortcuts(data.get('shortcuts')),data.get('reportIntervalMs'))
        if route=='/api/pair-answer':
            if not self.agent.pending or data.get('id')!=self.agent.pending['id']: raise ValueError('Pairing request expired')
            accepted=data.get('accept') is True
            key=data.get('passkey','')
            if accepted and self.agent.pending['kind']=='passkey' and (not isinstance(key,str) or len(key)!=6 or not key.isascii() or not key.isdigit()): raise ValueError('Enter the six digits shown by Windows')
            self.agent.resolve(accepted,int(key) if key else 0);return {'ok':True}
        raise ValueError('Unknown action')

def bridge_handler(controller,token,port):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def allowed(self):
            return self.headers.get('Host')=='127.0.0.1:'+str(port) and self.headers.get('Origin')=='null'

        def respond(self,status,payload):
            body=json.dumps(payload).encode()
            self.send_response(status)
            if self.allowed(): self.send_header('Access-Control-Allow-Origin','null')
            self.send_header('Cache-Control','no-store')
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(body)))
            self.end_headers();self.wfile.write(body)

        def do_OPTIONS(self):
            if not self.allowed(): self.respond(403,{'error':'Origin rejected'});return
            self.send_response(204);self.send_header('Access-Control-Allow-Origin','null')
            self.send_header('Access-Control-Allow-Methods','POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers','Authorization, Content-Type')
            self.send_header('Access-Control-Allow-Private-Network','true');self.end_headers()

        def do_POST(self):
            self.connection.settimeout(5)
            auth=self.headers.get('Authorization','')
            if not self.allowed() or not hmac.compare_digest(auth,'Bearer '+token):
                self.respond(403,{'error':'Access denied'});return
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=65536: raise ValueError('Invalid request size')
                if self.headers.get('Content-Type','').split(';')[0]!='application/json': raise ValueError('JSON required')
                data=json.loads(self.rfile.read(length))
                if not isinstance(data,dict): raise ValueError('Object required')
                done=threading.Event();result={}
                def invoke():
                    try: result['value']=controller.handle(self.path,data)
                    except Exception as error: result['error']=str(error)
                    done.set();return False
                GLib.idle_add(invoke)
                if not done.wait(8): raise ValueError('Bluetooth service did not respond')
                if 'error' in result: raise ValueError(result['error'])
                self.respond(200,result['value'])
            except (ValueError,TypeError,json.JSONDecodeError) as error:
                self.respond(400,{'error':str(error)})
    return Handler

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--app-home',required=True);parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--state-dir',default='/var/lib/smartkeyboard-bluetooth')
    parser.add_argument('--report-interval-ms',type=int,default=5,help='Report pacing, 3–30ms; 5ms targets about 100 characters/second')
    args=parser.parse_args();home=Path(args.app_home).resolve()
    if not 3<=args.report_interval_ms<=30: parser.error('--report-interval-ms must be between 3 and 30')
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(message)s')
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus=dbus.SystemBus();objects=dbus.Interface(bus.get_object('org.bluez','/'),OM).GetManagedObjects()
    adapters=[str(p) for p,v in objects.items() if 'org.bluez.GattManager1' in v and 'org.bluez.LEAdvertisingManager1' in v]
    if len(adapters)!=1: raise RuntimeError('Exactly one GATT/advertising adapter is required')
    controller=Controller(bus,adapters[0],args.report_interval_ms);controller.audio_home=home;controller.props.Set(ADAPTER,'Powered',dbus.Boolean(True))
    logging.info('Keyboard pacing: %dms/report; target %.1f characters/second',args.report_interval_ms,1000/(2*args.report_interval_ms))
    application=Application(bus,controller);advertisement=Advertisement(bus)
    manager=dbus.Interface(bus.get_object('org.bluez','/org/bluez'),'org.bluez.AgentManager1')
    manager.RegisterAgent(controller.agent.get_path(),'KeyboardDisplay')
    manager.RequestDefaultAgent(controller.agent.get_path())
    state=Path(args.state_dir);state.mkdir(mode=0o700,parents=True,exist_ok=True)
    token_file=state/'bridge-token'
    if token_file.exists(): token=token_file.read_text().strip()
    else:
        token=secrets.token_urlsafe(32);token_file.write_text(token);token_file.chmod(0o600)
    server=ThreadingHTTPServer(('127.0.0.1',args.port),bridge_handler(controller,token,args.port));server.daemon_threads=True
    # Token is readable only through a local file, never exposed by HTTP.
    config=home/'src'/'bridge-config.js'
    flags=os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW
    with os.fdopen(os.open(config,flags,0o600),'w') as stream:
        stream.write('window.SMARTKEYBOARD_BRIDGE = '+json.dumps({'url':'http://127.0.0.1:'+str(args.port),'token':token})+';\n')
        os.fchmod(stream.fileno(),0o600)
        if os.geteuid()==0: os.fchown(stream.fileno(),home.stat().st_uid,home.stat().st_gid)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    loop=GLib.MainLoop()
    def bluez_changed(name,old,new):
        if old:
            controller.registered=False;controller.error='BlueZ restarted; re-registering keyboard'
            controller.queue.clear();loop.quit()
    bus.add_signal_receiver(bluez_changed,bus_name='org.freedesktop.DBus',
                            dbus_interface='org.freedesktop.DBus',signal_name='NameOwnerChanged',arg0='org.bluez')
    def fail(error):
        controller.error=str(error);logging.error('BlueZ registration failed: %s',error);loop.quit()
    def advertised():
        controller.registered=True;controller.error='';controller.last_message='Smart Keyboard BLE ready; open pairing on touchscreen'
        logging.info(controller.last_message)
    def registered():
        dbus.Interface(bus.get_object('org.bluez',adapters[0]),'org.bluez.LEAdvertisingManager1').RegisterAdvertisement(
            advertisement.get_path(),{},reply_handler=advertised,error_handler=fail)
    dbus.Interface(bus.get_object('org.bluez',adapters[0]),'org.bluez.GattManager1').RegisterApplication(
        application.get_path(),{},reply_handler=registered,error_handler=fail)
    def shutdown(*unused): GLib.idle_add(loop.quit)
    signal.signal(signal.SIGTERM,shutdown);signal.signal(signal.SIGINT,shutdown)
    try: loop.run()
    finally:
        if hasattr(controller,'audio'):controller.audio.stop_meter()
        controller.agent.resolve(False);controller.close_pairing()
        controller.input.emit(RELEASE);controller.boot_input.emit(RELEASE)
        server.shutdown();server.server_close()
    if controller.error: raise RuntimeError(controller.error)

if __name__=='__main__': main()
