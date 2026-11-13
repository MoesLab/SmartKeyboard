#!/usr/bin/env python3
"""Save/restore project code only; never touches profiles, saved buttons or drivers."""
import argparse
import json
import os
from pathlib import Path
import shutil
import tempfile


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--restore',type=Path)
    args=parser.parse_args();app=Path.home()/'SmartKeyboard'
    if hasattr(os,'geteuid') and os.geteuid()==0:parser.error('Run as radxa, without sudo.')
    if app.is_symlink() or any((app/name).is_symlink() for name in ('src','backend','scripts')):parser.error('Unexpected application code symlink.')
    if args.restore:
        backup=args.restore.resolve(strict=True);root=(app/'backups').resolve()
        if root not in backup.parents:parser.error('Restore checkpoint must be inside ~/SmartKeyboard/backups.')
        manifest=json.loads((backup/'checkpoint.json').read_text())
        if manifest.get('format')!='SmartKeyboardCodeCheckpoint':parser.error('Not a recognized code checkpoint.')
        for name in ('src','backend','scripts'):
            if not (backup/name).is_dir() or (backup/name).is_symlink():parser.error('Incomplete checkpoint.')
        for name in ('src','backend','scripts'):shutil.copytree(backup/name,app/name,dirs_exist_ok=True)
        print('Previous project code restored. Saved browser data, headset driver, models and preferences were untouched.')
        print('Apply backend: sudo bash ~/SmartKeyboard/scripts/install-bluetooth-keyboard.sh')
        print('Refresh GUI: bash ~/SmartKeyboard/scripts/restart-kiosk.sh')
    else:
        for name in ('src','backend','scripts'):
            if not (app/name).is_dir():parser.error('Missing project '+name)
        (app/'backups').mkdir(exist_ok=True)
        backup=Path(tempfile.mkdtemp(prefix='pre-stt-',dir=str(app/'backups')));os.chmod(backup,0o700)
        for name in ('src','backend','scripts'):shutil.copytree(app/name,backup/name,ignore=shutil.ignore_patterns('__pycache__'))
        (backup/'checkpoint.json').write_text(json.dumps({'format':'SmartKeyboardCodeCheckpoint','version':1}))
        print('Code checkpoint:',backup)
        print('Keep this path. It includes the local bridge config; do not upload it to GitHub.')
        print('Restore: python3 ~/SmartKeyboard-source/scripts/stt-checkpoint.py --restore '+str(backup))
    return 0


if __name__=='__main__':raise SystemExit(main())
