import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


def load(name,filename):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).with_name(filename))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


restore=load('restore_headset','restore-headset.py')
persist=load('persist_headset','persist-headset-setup.py')
CONFIG={'version':1,'address':restore.ADDRESS,'profile':restore.PROFILE,'kernel':'test-kernel','srcversion':'TEST',
        'output':{'volume':50,'muted':False},'input':{'volume':75,'muted':False}}


class PersistenceTests(unittest.TestCase):
    def test_restore_targets_only_headset_and_restores_levels(self):
        calls=[];now=[0]
        def run(args,timeout):
            calls.append(args)
            if args==['pactl','list','short','sinks']:return restore.SINK
            if args==['pactl','list','short','sources']:return restore.SOURCE
            return ''
        restore.restore(CONFIG,run,driver_check=lambda config:None,clock=lambda:now[0],sleep=lambda seconds:now.__setitem__(0,now[0]+seconds))
        self.assertIn(['pactl','set-sink-volume',restore.SINK,'50%'],calls)
        self.assertIn(['pactl','set-source-volume',restore.SOURCE,'75%'],calls)
        self.assertEqual(sum(call[-1]==restore.PROFILE for call in calls),1)
        self.assertFalse(any('default' in ' '.join(call) or 'systemctl' in call for call in calls))

    def test_wrong_driver_never_connects_or_switches_profile(self):
        now=[0];calls=[]
        def fail(config):raise ValueError('wrong driver')
        with self.assertRaises(TimeoutError):
            restore.restore(CONFIG,lambda *args:calls.append(args),driver_check=fail,clock=lambda:now[0],sleep=lambda seconds:now.__setitem__(0,now[0]+seconds))
        self.assertEqual(calls,[]);self.assertEqual(now[0],90)

    def test_busy_voice_profile_has_only_two_attempts(self):
        now=[0];attempts=[]
        def run(args,timeout):
            if args[-1]==restore.PROFILE:
                attempts.append(args);raise subprocess.CalledProcessError(1,args)
            return ''
        with self.assertRaises(subprocess.CalledProcessError):
            restore.restore(CONFIG,run,driver_check=lambda config:None,clock=lambda:now[0],sleep=lambda seconds:now.__setitem__(0,now[0]+seconds))
        self.assertEqual(len(attempts),2)

    def test_install_preflight_requires_currently_loaded_module(self):
        with tempfile.TemporaryDirectory() as directory:
            module=Path(directory)/'aic_btusb.ko';module.write_bytes(b'fixture')
            module.with_name('aic_btusb.c').write_text('SMARTKEYBOARD_SCO_TEST_V1')
            module.with_name('smartkeyboard-sco-test.json').write_text(json.dumps({'experimental':True}))
            fields={'name':'aic_btusb','vermagic':'test-kernel SMP','depends':'bluetooth','srcversion':'TEST'}
            info=lambda field,path:fields[field]
            self.assertEqual(persist.preflight(module,'test-kernel','TEST',info),'TEST')
            with self.assertRaises(ValueError):persist.preflight(module,'test-kernel','OLD',info)
            with self.assertRaises(ValueError):persist.preflight(module,'wrong-kernel','TEST',info)

    def test_config_rejects_other_devices_and_invalid_levels(self):
        for bad in [dict(CONFIG,address='AA:BB:CC:DD:EE:FF'),dict(CONFIG,profile='something'),dict(CONFIG,input={'volume':101,'muted':False})]:
            with self.assertRaises(ValueError):restore.validate_config(bad)


if __name__=='__main__':unittest.main()
