"""Transport-independent tests; actual BlueZ registration needs the Radxa."""
import collections
import http.client
import importlib
import json
import sys
import threading
import types
import unittest
from unittest.mock import Mock

# D-Bus is Linux-only. Model its decorators/types to test our state machine
# and object hierarchy here, without pretending to test Bluetooth hardware.
dbus=types.ModuleType('dbus')
dbus.service=types.ModuleType('dbus.service')
class Object:
    def __init__(self,bus,path): self.exported_path=path
dbus.service.Object=Object
dbus.service.method=lambda *a,**kw: lambda fn:fn
dbus.service.signal=lambda *a,**kw: lambda fn:fn
dbus.exceptions=types.ModuleType('dbus.exceptions')
dbus.exceptions.DBusException=type('DBusException',(Exception,),{})
dbus.mainloop=types.ModuleType('dbus.mainloop');dbus.mainloop.glib=types.ModuleType('dbus.mainloop.glib')
dbus.ObjectPath=str;dbus.Byte=int;dbus.UInt16=int;dbus.UInt32=int;dbus.Boolean=bool
dbus.Array=lambda value,**kw:list(value)
gi=types.ModuleType('gi');repository=types.ModuleType('gi.repository')
repository.GLib=types.SimpleNamespace(idle_add=lambda fn:fn())
for name,module in [('dbus',dbus),('dbus.service',dbus.service),('dbus.exceptions',dbus.exceptions),('dbus.mainloop',dbus.mainloop),('dbus.mainloop.glib',dbus.mainloop.glib),('gi',gi),('gi.repository',repository)]: sys.modules[name]=module
keyboard=importlib.import_module('bluetooth_keyboard')

def controller():
    instance=keyboard.Controller.__new__(keyboard.Controller)
    instance.registered=True;instance.error='';instance.adapter='/org/bluez/hci0';instance.protocol=1;instance.suspended=False
    instance.input=types.SimpleNamespace(notifying=True,emit=Mock());instance.boot_input=types.SimpleNamespace(notifying=False,emit=Mock())
    instance.objects={instance.adapter+'/dev_PC':{keyboard.DEVICE:{'Connected':True,'Paired':True,'Alias':'Test PC'}}}
    instance.queue=collections.deque();instance.queue_target=None;instance.last_message='';instance.pair_until=0;instance.pair_display=None
    instance.agent=types.SimpleNamespace(pending=None)
    return instance

class BluetoothLogic(unittest.TestCase):
    def test_queue_stops_on_disconnect(self):
        item=controller();item.enqueue(keyboard.encode_text('ab'));item.tick()
        item.objects[item.adapter+'/dev_PC'][keyboard.DEVICE]['Connected']=False
        item.tick();self.assertEqual(len(item.queue),0)
        self.assertEqual(item.input.emit.call_args.args[0],keyboard.RELEASE)

    def test_zero_or_multiple_hosts_cannot_send(self):
        for kind in ('unpaired','multiple','unsubscribed'):
            item=controller()
            if kind=='unpaired': item.objects[item.adapter+'/dev_PC'][keyboard.DEVICE]['Paired']=False
            if kind=='multiple': item.objects[item.adapter+'/dev_OTHER']={keyboard.DEVICE:{'Connected':True,'Paired':True}}
            if kind=='unsubscribed': item.input.notifying=False
            with self.assertRaises(ValueError): item.enqueue(keyboard.encode_text('a'))
            self.assertFalse(item.queue)

    def test_gatt_paths_and_keyboard_report_reference(self):
        item=controller();app=keyboard.Application(None,item);objects=app.GetManagedObjects()
        self.assertEqual(app.get_path(),keyboard.ROOT)
        self.assertTrue(any(v.get(keyboard.SERVICE,{}).get('UUID')==keyboard.uuid('1812') for v in objects.values()))
        report=item.input
        self.assertEqual(report.descriptors[0].ReadValue({}),[1,1])
        self.assertIn('encrypt-read',report.flags)
        self.assertEqual(len(report.value),8)
        self.assertTrue(all(path.startswith(keyboard.ROOT+'/service') for path in objects))
        self.assertEqual(keyboard.Advertisement(None).get_path(),keyboard.ROOT+'/advertisement')

    def test_pairing_requires_open_window(self):
        item=controller();agent=keyboard.PairingAgent(None,item);reply=Mock();error=Mock()
        agent.request('/dev/PC','confirm',reply,error,'123456');error.assert_called_once();reply.assert_not_called()

    def test_http_requires_origin_and_secret(self):
        item=controller();server=keyboard.ThreadingHTTPServer(('127.0.0.1',0),keyboard.bridge_handler(item,'secret',0))
        port=server.server_address[1]
        # Handler's port is fixed intentionally; exercise a second bound server.
        server.server_close()
        server=keyboard.ThreadingHTTPServer(('127.0.0.1',port),keyboard.bridge_handler(item,'secret',port))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def request(origin,token,route='/api/status',payload=None):
            connection=http.client.HTTPConnection('127.0.0.1',port,timeout=3)
            connection.request('POST',route,json.dumps(payload or {}),{'Origin':origin,'Authorization':'Bearer '+token,'Content-Type':'application/json'})
            response=connection.getresponse();data=json.loads(response.read());connection.close();return response.status,data
        try:
            self.assertEqual(request('https://example.com','secret')[0],403)
            self.assertEqual(request('null','wrong')[0],403)
            self.assertEqual(request('null','secret')[0],200)
            code,data=request('null','secret','/api/send',{'text':'Hello Ω'})
            self.assertEqual(code,400);self.assertFalse(item.queue)
            code,data=request('null','secret','/api/macro',{'shortcuts':['Ctrl+C']})
            self.assertEqual(code,200);self.assertEqual(len(item.queue),2)
        finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__': unittest.main()
