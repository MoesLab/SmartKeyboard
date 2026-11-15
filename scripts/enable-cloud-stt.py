#!/usr/bin/env python3
"""Select direct Radxa cloud or the existing paired Zima cloud route explicitly."""
import argparse
import getpass
import json
import os
from pathlib import Path
import tempfile


def save_private(path,text):
    if path.is_symlink() or path.parent.is_symlink():raise ValueError('Unexpected private configuration link.')
    fd,temporary=tempfile.mkstemp(prefix='.cloud-setting-',dir=str(path.parent))
    try:
        with os.fdopen(fd,'w') as stream:stream.write(text)
        os.replace(temporary,path)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disable',action='store_true')
    parser.add_argument('--direct',action='store_true',help='Record and upload on Radxa, without ZimaBoard.')
    parser.add_argument('--replace-key',action='store_true')
    args=parser.parse_args()
    if os.geteuid()==0:parser.error('Run as radxa, without sudo.')
    root=Path.home()/'SmartKeyboard/config';root.mkdir(exist_ok=True)
    route='direct' if args.direct else 'zima'
    if not args.disable:
        if args.direct:
            path=root/'openai-api-key'
            if not path.exists() or args.replace_key:
                key=getpass.getpass('Paste OpenAI API key ONCE, then Enter (hidden): ').strip()
                if not key.startswith('sk-') or key.count('sk-')!=1 or any(c.isspace() for c in key):parser.error('Invalid key entry. Existing files unchanged.')
                save_private(path,key)
            else:
                if path.is_symlink():parser.error('Unexpected key link.')
                key=path.read_text().strip()
                if not key.startswith('sk-') or key.count('sk-')!=1 or any(c.isspace() for c in key):parser.error('Invalid saved key. Retry with --direct --replace-key.')
                path.chmod(0o600)
        elif not (root/'zima-stt.json').is_file():parser.error('ZimaBoard pairing file required for the Zima route.')
    save_private(root/'cloud-stt.json',json.dumps({'enabled':not args.disable,'version':1,'route':route}))
    print('Cloud disabled; Local configuration preserved.' if args.disable else 'Cloud enabled: Radxa -> OpenAI directly. ZimaBoard is not needed for Cloud.' if args.direct else 'Cloud enabled: Radxa -> paired ZimaBoard -> OpenAI.')
    print('No API request made. Audio uploads still require Cloud Dictate confirmation.')


if __name__=='__main__':main()
