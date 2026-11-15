"""Explicit Radxa microphone choice. Never silently substitutes another input."""
import json
import os
from pathlib import Path
import tempfile

HEADSET='bluez_source.C0_86_B3_F2_E8_96.headset_head_unit'


def allowed_input(name):
    return isinstance(name,str) and (name==HEADSET or name.startswith('alsa_input.usb-')) and not name.endswith('.monitor')


def selected(app):
    path=Path(app)/'config/audio-input.json'
    if not path.exists():return HEADSET
    data=json.loads(path.read_text())
    if data.get('version')!=1 or not allowed_input(data.get('source')):raise ValueError('Invalid saved microphone selection.')
    return data['source']


def save(app,source):
    if not allowed_input(source):raise ValueError('Select the headset or a detected USB microphone.')
    path=Path(app)/'config/audio-input.json';path.parent.mkdir(exist_ok=True)
    if path.is_symlink() or path.parent.is_symlink():raise ValueError('Unexpected microphone configuration link.')
    fd,temporary=tempfile.mkstemp(prefix='.audio-input-',dir=str(path.parent))
    try:
        with os.fdopen(fd,'w') as stream:
            json.dump({'version':1,'source':source},stream)
            owner=Path(app).stat()
            if hasattr(os,'fchown'):os.fchown(stream.fileno(),owner.st_uid,owner.st_gid)
        os.replace(temporary,path)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)


def verify_headset_driver(app):
    try:
        expected=json.loads((Path(app)/'config/headset-startup.json').read_text())
        loaded=Path('/sys/module/aic_btusb/srcversion').read_text().strip()
        if expected.get('kernel')!=os.uname().release or loaded!=expected.get('srcversion') or loaded!='049CCA2FA2A06FBA0732370':
            raise ValueError('Driver mismatch')
    except (OSError,ValueError,TypeError,AttributeError):
        raise ValueError('Load the persisted, tested headset driver before microphone capture.')
