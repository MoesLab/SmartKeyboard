#!/usr/bin/env python3
"""Persist the currently loaded/tested SCO driver and saved OpenComm2 setup."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

UNIT_NAME='smartkeyboard-headset-restore.service'
MARKER='# SmartKeyboard managed headset restore'


def run(args,**kwargs):
    return subprocess.run(args,check=True,text=True,capture_output=True,**kwargs).stdout.strip()


def write_atomic(path,data,mode=0o644,owner=None):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,temp=tempfile.mkstemp(prefix='.smartkeyboard-',dir=str(path.parent))
    try:
        with os.fdopen(fd,'wb') as stream:
            stream.write(data);stream.flush();os.fsync(stream.fileno())
            os.fchmod(stream.fileno(),mode)
            if owner:os.fchown(stream.fileno(),*owner)
        os.replace(temp,str(path))
    finally:
        if os.path.exists(temp):os.unlink(temp)


def preflight(module,kernel,loaded,modinfo):
    module=module.resolve(strict=True)
    if modinfo('name',module)!='aic_btusb':raise ValueError('Unexpected module name.')
    if modinfo('vermagic',module).split()[0]!=kernel:raise ValueError('Module does not match the running kernel.')
    if 'bluetooth' not in modinfo('depends',module).split(','):raise ValueError('Expected a Linux Bluetooth module.')
    version=modinfo('srcversion',module)
    if not loaded or version!=loaded:raise ValueError('Supplied module is not the currently loaded test module. Nothing changed.')
    source=module.with_name('aic_btusb.c').read_text()
    if 'SMARTKEYBOARD_SCO_TEST_V1' not in source:raise ValueError('Missing tested SCO patch marker.')
    provenance=json.loads(module.with_name('smartkeyboard-sco-test.json').read_text())
    if provenance.get('experimental') is not True:raise ValueError('Unrecognized test-build provenance.')
    return version


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('module',type=Path)
    args=parser.parse_args()
    if os.geteuid()!=0 or not os.environ.get('SUDO_USER') or os.environ['SUDO_USER']=='root':
        parser.error('Run with sudo from the radxa account.')
    backup=None;changed=False;saved={};enabled_before=False
    try:
        import pwd
        account=pwd.getpwnam(os.environ['SUDO_USER'])
        app=Path(account.pw_dir)/'SmartKeyboard'
        if app.is_symlink() or app.stat().st_uid!=account.pw_uid:raise ValueError('Unexpected application directory ownership.')
        print("Checking the loaded test driver and headset setup...",flush=True)
        kernel=os.uname().release;module=args.module.resolve(strict=True)
        modinfo=lambda field,path:run(['/sbin/modinfo','-F',field,str(path)])
        version=preflight(module,kernel,Path('/sys/module/aic_btusb/srcversion').read_text().strip(),modinfo)
        destination=Path('/lib/modules')/kernel/'updates/smartkeyboard/aic_btusb_usb.ko'
        depmod_config=Path('/etc/depmod.d/99-smartkeyboard-bluetooth.conf')
        if destination.is_symlink() or not destination.is_file() or depmod_config.is_symlink():raise ValueError('Expected existing project driver override was not found.')
        expected='override aic_btusb_usb '+kernel+' updates/smartkeyboard'
        lines=depmod_config.read_text().splitlines()
        if not lines or not lines[0].startswith('# SmartKeyboard:') or [line.strip() for line in lines if line.strip() and not line.startswith('#')]!=[expected]:
            raise ValueError('Unrecognized depmod configuration; nothing changed.')
        unit=Path('/etc/systemd/system')/UNIT_NAME
        if unit.is_symlink() or (unit.exists() and not unit.read_text().startswith(MARKER)):
            raise ValueError('Unrecognized existing headset startup service.')
        helper=Path(__file__).with_name('restore-headset.py')
        if not helper.is_file():raise ValueError('Missing restore-headset.py next to this installer.')
        config=app/'config/headset-startup.json'
        if config.is_symlink() or config.parent.is_symlink():raise ValueError('Unexpected headset configuration symlink.')
        sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'backend'))
        from headset_audio import HeadsetAudio
        audio=HeadsetAudio(app).status()
        outputs=[d for d in audio['outputs'] if d['name'].endswith('.headset_head_unit')]
        inputs=[d for d in audio['inputs'] if d['name'].endswith('.headset_head_unit')]
        if not outputs or not inputs:raise ValueError('Connect the headset in the tested microphone mode before saving setup.')
        settings={'version':1,'address':'C0:86:B3:F2:E8:96','profile':'headset_head_unit','kernel':kernel,'srcversion':version}
        for kind,device in [('output',outputs[0]),('input',inputs[0])]:
            settings[kind]={'volume':max(0,min(100,device['volume'])),'muted':device['muted']}
        installed_helper=Path('/opt/smartkeyboard-bluetooth/restore-headset.py')
        initrd=Path('/boot')/('initrd.img-'+kernel);refresh_initrd=False
        if initrd.exists():
            listing=shutil.which('lsinitramfs')
            if not listing:raise ValueError('Cannot inspect the existing initramfs; lsinitramfs is required before persisting this driver.')
            refresh_initrd=bool(re.search(r'aic_btusb[^/]*\.ko',run([listing,str(initrd)])))
            if refresh_initrd and (not shutil.which('update-initramfs') or initrd.is_symlink()):
                raise ValueError('Existing initramfs needs a driver update; verify its layout/tools before continuing.')
        state=Path('/var/lib/smartkeyboard-bluetooth/driver-backups')
        state.mkdir(mode=0o700,parents=True,exist_ok=True)
        if state.is_symlink():raise ValueError('Unexpected driver backup directory.')
        if refresh_initrd and shutil.disk_usage(state).free < initrd.stat().st_size*3+20_000_000:
            raise ValueError('Insufficient free space to back up and update initramfs.')
        backup=Path(tempfile.mkdtemp(prefix=kernel+'-',dir=str(state)));os.chmod(backup,0o700)
        files=[destination,depmod_config,unit,installed_helper,config]
        if refresh_initrd:files.append(initrd)
        for i,path in enumerate(files):
            if path.is_symlink():raise ValueError('Refusing to replace a symlink: '+str(path))
            if path.exists():
                target=backup/('file-'+str(i));shutil.copy2(path,target)
                saved[str(path)]={'backup':str(target),'mode':path.stat().st_mode&0o777,'uid':path.stat().st_uid,'gid':path.stat().st_gid}
            else:saved[str(path)]=None
        enabled_before=subprocess.run(['systemctl','is-enabled',UNIT_NAME],capture_output=True,text=True).stdout.strip()=='enabled'
        (backup/'manifest.json').write_text(json.dumps({'kernel':kernel,'files':saved,'unitEnabled':enabled_before},indent=2))
        print("Backup saved:",backup,flush=True)
        print("Saving the tested module for future boots...",flush=True)
        changed=True
        write_atomic(destination,module.read_bytes())
        run(['/sbin/depmod','-a',kernel])
        if run(['/sbin/modinfo','-n','aic_btusb_usb'])!=str(destination) or modinfo('srcversion',destination)!=version:
            raise ValueError('Persistent module selection verification failed.')
        if refresh_initrd:
            run([shutil.which('update-initramfs'),'-u','-k',kernel],timeout=180)
            if 'updates/smartkeyboard/aic_btusb_usb.ko' not in run([shutil.which('lsinitramfs'),str(initrd)]):
                raise ValueError('Updated initramfs did not include the project driver.')
        write_atomic(installed_helper,helper.read_bytes())
        write_atomic(config,(json.dumps(settings,indent=2)+'\n').encode(),0o600,(account.pw_uid,account.pw_gid))
        unit_text=MARKER+'''\n[Unit]
Description=Restore tested Smart Keyboard headset after startup
Wants=bluetooth.service
After=bluetooth.service smartkeyboard-bluetooth.service

[Service]
Type=simple
User='''+account.pw_name+'''
Environment=XDG_RUNTIME_DIR=/run/user/'''+str(account.pw_uid)+'''
Environment=PULSE_SERVER=unix:/run/user/'''+str(account.pw_uid)+'''/pulse/native
ExecStart=/usr/bin/python3 /opt/smartkeyboard-bluetooth/restore-headset.py --config "'''+str(config)+'''"
RemainAfterExit=yes
TimeoutStopSec=10
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
'''
        write_atomic(unit,unit_text.encode())
        run(['systemctl','daemon-reload']);run(['systemctl','enable',UNIT_NAME])
        print('Persistent tested module:',destination)
        print('Expected loaded version after reboot:',version)
        print('Headset startup restore enabled; listening/microphone levels saved.')
        print('Backup:',backup)
        print('No running driver reloaded; Wi-Fi, EZ Signage, display and browser profiles unchanged.')
        print('This driver is kernel-specific. Turn on the headset for the next boot test.')
        return 0
    except (OSError,ValueError,subprocess.SubprocessError) as error:
        print('Stopped:',error,file=sys.stderr)
        if changed:
            try:
                if not enabled_before:subprocess.run(['systemctl','disable',UNIT_NAME],capture_output=True)
                for name,entry in saved.items():
                    path=Path(name)
                    if entry:write_atomic(path,Path(entry['backup']).read_bytes(),entry['mode'],(entry['uid'],entry['gid']))
                    elif path.exists():path.unlink()
                run(['/sbin/depmod','-a',os.uname().release]);run(['systemctl','daemon-reload'])
                print('Previous files restored; the running test driver was not unloaded.',file=sys.stderr)
            except Exception as rollback_error:print('Rollback needs attention:',rollback_error,'Backup:',backup,file=sys.stderr)
        return 1


if __name__=='__main__':raise SystemExit(main())
