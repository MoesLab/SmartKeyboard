import unittest
from unittest.mock import Mock
from headset_audio import HeadsetAudio,parse_devices

SINKS='''Sink #0
    Name: alsa_output.HDMI
    Description: HDMI
    Mute: no
    Volume: front-left: 65536 / 100% / 0.00 dB
Sink #2
    Name: bluez_sink.C0_86_B3_F2_E8_96.headset_head_unit
    Description: OpenComm2 by Shokz
    Mute: no
    Volume: mono: 32768 / 50% / -18.06 dB
Sink #3
    Name: bluez_sink.AA_BB_CC_DD_EE_FF.a2dp_sink
    Description: Other speaker
    Mute: no
    Volume: front-left: 65536 / 100% / 0.00 dB
'''
SOURCES='''Source #0
    Name: bluez_sink.C0_86_B3_F2_E8_96.headset_head_unit.monitor
    Description: Monitor
    Mute: no
    Volume: mono: 65536 / 100% / 0.00 dB
Source #3
    Name: bluez_source.C0_86_B3_F2_E8_96.headset_head_unit
    Description: OpenComm2 by Shokz
    Mute: yes
    Volume: mono: 49152 / 75% / -7.50 dB
'''


class HeadsetAudioTests(unittest.TestCase):
    def helper(self):
        runner=Mock(side_effect=lambda args:SINKS if args==['list','sinks'] else SOURCES if args==['list','sources'] else '')
        return HeadsetAudio(None,runner),runner

    def test_only_shokz_real_endpoints_are_exposed(self):
        helper,_=self.helper();status=helper.status()
        self.assertEqual(len(status['outputs']),1);self.assertEqual(len(status['inputs']),1)
        self.assertEqual(status['outputs'][0]['volume'],50)
        self.assertTrue(status['inputs'][0]['muted'])
        self.assertEqual(parse_devices('', 'input'),[])

    def test_volume_writes_are_clamped_and_targeted(self):
        for kind,prefix,operation in [('input','bluez_source.','set-source-volume'),('output','bluez_sink.','set-sink-volume')]:
            helper,runner=self.helper();name=prefix+'C0_86_B3_F2_E8_96.headset_head_unit'
            helper.set_volume({'kind':kind,'name':name,'volume':25})
            self.assertIn(unittest.mock.call([operation,name,'25%']),runner.call_args_list)
            self.assertTrue(all(args.args[0][0] in ('list',operation) for args in runner.call_args_list))

    def test_invalid_gain_and_non_headset_targets_never_write(self):
        name='bluez_sink.C0_86_B3_F2_E8_96.headset_head_unit'
        samples=[{'kind':'output','name':name,'volume':v} for v in (-1,101,True,'50',50.0)]
        samples += [{'kind':'output','name':n,'volume':50} for n in ('alsa_output.HDMI','bluez_sink.AA_BB_CC_DD_EE_FF.a2dp_sink',name+'; reboot')]
        samples += [{'kind':'input','name':name+'.monitor','volume':50}]
        for data in samples:
            helper,runner=self.helper()
            with self.assertRaises(ValueError):helper.set_volume(data)
            self.assertFalse(any(call.args[0][0].startswith('set-') for call in runner.call_args_list))

    def test_missing_microphone_does_not_switch_profiles(self):
        runner=Mock(side_effect=lambda args:SINKS if args==['list','sinks'] else '')
        helper=HeadsetAudio(None,runner)
        self.assertEqual(helper.status()['inputs'],[])
        self.assertTrue(all(call.args[0][0]=='list' for call in runner.call_args_list))


if __name__=='__main__':unittest.main()
