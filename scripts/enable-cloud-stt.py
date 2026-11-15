#!/usr/bin/env python3
"""Explicitly enable/disable cloud requests from this Radxa application only."""
import argparse
import json
import os
from pathlib import Path

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--disable',action='store_true')
args=parser.parse_args()
if os.geteuid()==0:parser.error('Run as radxa, without sudo.')
root=Path.home()/'SmartKeyboard/config'
if not (root/'zima-stt.json').is_file():parser.error('Private ZimaBoard pairing file is required first.')
path=root/'cloud-stt.json'
if path.is_symlink():parser.error('Unexpected configuration link.')
path.write_text(json.dumps({'enabled':not args.disable,'version':1}));path.chmod(0o600)
print('Cloud disabled. Local mode remains available.' if args.disable else 'Cloud enabled for explicit Dictate requests. Each recording requires upload confirmation; paid OpenAI transcription occurs on ZimaBoard.')
