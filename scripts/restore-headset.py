#!/usr/bin/env python3
"""Bounded, user-session OpenComm2 restore; requires the tested kernel driver."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time

ADDRESS='C0:86:B3:F2:E8:96'
CARD='bluez_card.C0_86_B3_F2_E8_96'
PROFILE='headset_head_unit'
SINK='bluez_sink.C0_86_B3_F2_E8_96.headset_head_unit'
SOURCE='bluez_source.C0_86_B3_F2_E8_96.headset_head_unit'


def validate_config(config):
    if config.get('version')!=1 or config.get('address')!=ADDRESS or config.get('profile')!=PROFILE:
        raise ValueError('Unrecognized headset startup configuration.')
    if not isinstance(config.get('kernel'),str) or not isinstance(config.get('srcversion'),str):
        raise ValueError('Missing tested driver identity.')
    for kind in ('output','input'):
        value=config.get(kind)
        if not isinstance(value,dict) or type(value.get('volume')) is not int or not 0<=value['volume']<=100 or type(value.get('muted')) is not bool:
            raise ValueError('Invalid saved headset level.')
    return config


def require_tested_driver(config):
    if os.uname().release!=config['kernel']:
        raise ValueError('Kernel changed; headset microphone auto-restore skipped. A matching tested driver is required.')
    loaded=Path('/sys/module/aic_btusb/srcversion').read_text().strip()
    if loaded!=config['srcversion']:
        raise ValueError('Tested Bluetooth driver is not loaded; microphone auto-restore skipped.')


def restore(config,run,driver_check=require_tested_driver,clock=time.monotonic,sleep=time.sleep):
    validate_config(config)
    deadline=clock()+90
    def pause(seconds):
        remaining=deadline-clock()
        if remaining<=0:raise TimeoutError("Startup restore deadline reached.")
        sleep(min(seconds,remaining))
    def command(arguments):
        remaining=deadline-clock()
        if remaining<=0:raise TimeoutError('Startup restore deadline reached.')
        return run(arguments,min(8,remaining))
    # Wait for PulseAudio and the boot-time module load. Never connect an audio
    # device while the original crashing driver is loaded.
    ready=False
    while clock()<deadline:
        try:
            driver_check(config)
            command(['pactl','info']);command(['bluetoothctl','show'])
            ready=True;break
        except (OSError,ValueError,subprocess.SubprocessError):pause(2)
    if not ready:raise TimeoutError('Desktop audio or the tested driver was unavailable within 90 seconds. Headset untouched.')
    connected=False
    while clock()<deadline:
        try:
            driver_check(config)
            command(['bluetoothctl','connect',ADDRESS]);connected=True;break
        except (OSError,ValueError,subprocess.SubprocessError):pause(5)
    if not connected:raise TimeoutError('Headset was unavailable at startup. Turn it on and restart this restore service.')
    pause(3)
    # Match the successful manual transition. Retry at most once, not forever.
    for attempt in range(2):
        try:
            driver_check(config)
            command(['pactl','set-card-profile',CARD,'a2dp_sink']);pause(2)
            driver_check(config)
            command(['pactl','set-card-profile',CARD,PROFILE])
            sinks=command(['pactl','list','short','sinks'])
            sources=command(['pactl','list','short','sources'])
            if SINK not in sinks or SOURCE not in sources:raise ValueError('Headset voice endpoints did not appear.')
            for kind,endpoint,set_volume,set_mute in [('output',SINK,'set-sink-volume','set-sink-mute'),('input',SOURCE,'set-source-volume','set-source-mute')]:
                command(['pactl',set_volume,endpoint,str(config[kind]['volume'])+'%'])
                command(['pactl',set_mute,endpoint,'1' if config[kind]['muted'] else '0'])
            return
        except (OSError,ValueError,subprocess.SubprocessError):
            if attempt==1:raise
            pause(5)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',required=True,type=Path)
    args=parser.parse_args()
    try:
        config=validate_config(json.loads(args.config.read_text()))
        def run(arguments,timeout):
            return subprocess.run(arguments,check=True,capture_output=True,text=True,timeout=timeout).stdout
        restore(config,run)
        print('OpenComm2 connected in microphone mode; saved listening/microphone levels restored.')
        return 0
    except (OSError,ValueError,TimeoutError,subprocess.SubprocessError) as error:
        print('Headset startup restore stopped:',error)
        return 1


if __name__=='__main__':raise SystemExit(main())
