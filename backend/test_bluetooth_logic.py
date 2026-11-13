"""Transport-independent tests; actual BlueZ registration needs the Radxa."""
import collections
import http.client
import importlib
import json
import sys
import threading
import types
import unittest
from unittest.mock import Mock, patch

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

    def test_delivery_progress_and_no_replay_after_disconnect(self):
        item=controller();result=item.enqueue(keyboard.encode_text('ab'))
        self.assertEqual(result['delivery']['state'],'queued')
        item.tick();item.tick()
        self.assertEqual(item.delivery['actionsSent'],1)
        item.objects[item.adapter+'/dev_PC'][keyboard.DEVICE]['Connected']=False
        item.tick();self.assertEqual(item.delivery['state'],'stopped')
        item.objects[item.adapter+'/dev_PC'][keyboard.DEVICE]['Connected']=True
        count=item.input.emit.call_count;item.tick()
        self.assertEqual(item.input.emit.call_count,count)
        self.assertFalse(item.queue)

    def test_delivery_completion_and_explicit_cancel(self):
        item=controller();item.enqueue(keyboard.encode_text('a'))
        item.tick();item.tick();self.assertEqual(item.delivery['state'],'sent')
        item.enqueue(keyboard.encode_text('ab'))
        result=item.handle('/api/cancel-send',{})
        self.assertEqual(result['delivery']['state'],'cancelled');self.assertFalse(item.queue)

    def test_unsupported_character_has_location_without_queue(self):
        item=controller()
        with self.assertRaisesRegex(ValueError,'line 2, column 1'):
            item.handle('/api/send',{'text':'Hello'+chr(10)+'ی'})
        self.assertFalse(item.queue)

    def test_speed_presets_retime_only_before_send(self):
        item=controller();item.report_interval_ms=5;item.report_timer=42
        with patch.object(keyboard.GLib,'timeout_add',return_value=43,create=True) as schedule, patch.object(keyboard.GLib,'source_remove',create=True) as remove:
            item.handle('/api/send',{'text':'Hello','reportIntervalMs':15})
            self.assertEqual(item.report_interval_ms,15)
            self.assertEqual(schedule.call_args.args[0],15);remove.assert_called_once_with(42)
            with self.assertRaises(ValueError):item.handle('/api/send',{'text':'X','reportIntervalMs':5})
            self.assertEqual(item.report_interval_ms,15);self.assertEqual(schedule.call_count,1)

    def test_speed_rejects_invalid_values_without_queue(self):
        for speed in (True,0,3,100,'5',5.0):
            item=controller()
            with self.assertRaises(ValueError):item.handle('/api/send',{'text':'Hello','reportIntervalMs':speed})
            self.assertFalse(item.queue)

    def test_headset_does_not_count_as_second_pc_or_stop_send(self):
        item=controller();item.enqueue(keyboard.encode_text('abc'))
        item.objects[item.adapter+'/dev_HEADSET']={keyboard.DEVICE:{'Connected':True,'Paired':True,'Class':0x240404,'Alias':'Shokz'}}
        self.assertTrue(item.ready());item.tick();self.assertEqual(len(item.queue),5)
        self.assertEqual(item.snapshot()['connectedHosts'],1)
        item.objects[item.adapter+'/dev_PC'][keyboard.DEVICE]['Connected']=False
        self.assertFalse(item.ready());item.tick();self.assertFalse(item.queue)
        self.assertEqual(item.snapshot()['connectedHosts'],0)

    def test_audio_icon_fallback_and_pc_audio_services(self):
        for icon in ('audio-headset','audio-headphones','audio-speakers'):
            self.assertTrue(keyboard.Controller.audio_accessory({'Icon':icon}))
        self.assertFalse(keyboard.Controller.audio_accessory({'Class':0x100,'Icon':'audio-headset'}))
        self.assertFalse(keyboard.Controller.audio_accessory({'UUIDs':[keyboard.uuid('110a'),keyboard.uuid('110b')]}))
        self.assertFalse(keyboard.Controller.audio_accessory({}))

    def test_audio_controls_cannot_interrupt_queued_hid(self):
        item=controller();item.audio=Mock();item.audio.status.return_value={'outputs':[],'inputs':[]}
        self.assertEqual(item.handle('/api/audio-status',{}),{'outputs':[],'inputs':[]})
        item.enqueue(keyboard.encode_text('Hello'))
        with self.assertRaises(ValueError):item.handle('/api/audio-volume',{'kind':'output','volume':50})
        item.audio.set_volume.assert_not_called();self.assertEqual(len(item.queue),10)

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

    def test_shutdown_confirmation_and_delayed_call(self):
        item=controller();item.bus=Mock();item.agent.resolve=Mock();item.close_pairing=Mock()
        manager=Mock();manager.CanPowerOff.return_value='yes'
        with patch.object(keyboard.dbus,'Interface',return_value=manager,create=True), patch.object(keyboard.GLib,'timeout_add',create=True) as schedule:
            with self.assertRaises(ValueError): item.handle('/api/shutdown',{})
            manager.PowerOff.assert_not_called();schedule.assert_not_called()
            item.queue.extend(keyboard.encode_text('a'))
            self.assertTrue(item.handle('/api/shutdown',{'confirm':True})['ok'])
            self.assertTrue(item.shutdown_pending);self.assertFalse(item.queue)
            manager.PowerOff.assert_not_called()
            self.assertEqual(schedule.call_args.args[0],1500)
            with self.assertRaises(ValueError): item.handle('/api/send',{'text':'x'})
            schedule.call_args.args[1]()
            self.assertEqual(manager.PowerOff.call_args.args,(False,))
            manager.PowerOff.call_args.kwargs['error_handler'](RuntimeError('inhibited'))
            self.assertFalse(item.shutdown_pending);self.assertIn('inhibited',item.shutdown_error)

    def test_shutdown_authorization_failure_keeps_queue(self):
        item=controller();item.bus=Mock();manager=Mock();manager.CanPowerOff.return_value='no'
        item.queue.extend(keyboard.encode_text('a'));count=len(item.queue)
        with patch.object(keyboard.dbus,'Interface',return_value=manager,create=True):
            with self.assertRaises(ValueError): item.handle('/api/shutdown',{'confirm':True})
        self.assertEqual(len(item.queue),count);manager.PowerOff.assert_not_called()

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
