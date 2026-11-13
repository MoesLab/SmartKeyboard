#!/usr/bin/env python3
"""Prepare/build an isolated experimental AIC BlueZ module; never load/install it."""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


def patch_source(source, header):
    settings = re.findall(r'^\s*#define\s+CONFIG_BLUEDROID\s+(\d+)', header, re.M)
    if not settings or any(value != '0' for value in settings):
        raise ValueError('Expected the already-working CONFIG_BLUEDROID=0 source. No patch applied.')
    if not re.search(r'^\s*#define\s+SCO_NUM\s+hdev->conn_hash\.sco_num\s*$', header, re.M):
        raise ValueError('Unexpected SCO counter definition. No patch applied.')
    if 'SMARTKEYBOARD_SCO_TEST_V1' in source:
        raise ValueError('This source is already patched; supply the original working build directory.')
    event = re.search(r'static\s+void\s+check_sco_event\s*\(struct urb \*urb\).*?^}', source, re.S | re.M)
    if not event or event.group().count('SCO_NUM++;') != 1 or event.group().count('SCO_NUM--;') != 1:
        raise ValueError('Unexpected voice event handler. No patch applied.')
    writes = re.findall(r'(?m)^([ \t]*)SCO_NUM\s*(\+\+|--|=\s*0);[ \t]*$', source)
    if sorted(re.sub(r'\s+', '', op) for _, op in writes) != ['++', '--', '=0']:
        raise ValueError('Unexpected counter writes. No patch applied.')

    def guard_counter(match):
        indent, operation = match.group(1), match.group(2)
        return ('#if CONFIG_BLUEDROID\n' + indent + 'SCO_NUM' + operation + ';\n'
                '#endif /* BlueZ/Linux owns its connection counter. */')

    patched = re.sub(r'(?m)^([ \t]*)SCO_NUM\s*(\+\+|--|=\s*0);[ \t]*$', guard_counter, source)
    # Scope the ownership correction to the exact SCO transmission branch.
    sco = re.search(r'(case HCI_SCODATA_PKT:\s*print_sco\(skb,\s*1\);)(.*?)(hdev->stat\.sco_tx\+\+;)', patched, re.S)
    if not sco:
        raise ValueError('Expected SCO send branch was not found. No patch applied.')
    body = sco.group(2)
    if body.count('kfree(skb);') != 2 or body.count('return -ENODEV;') != 1 or body.count('return -ENOMEM;') != 1:
        raise ValueError('Unexpected SCO error ownership. No patch applied.')
    body = re.sub(r'(?m)^([ \t]*)kfree\(skb\);',
                  lambda m: '#if CONFIG_BLUEDROID\n' + m.group(1) + 'kfree(skb);\n'
                  '#endif /* BlueZ caller frees skb when send returns an error. */', body)
    patched = patched[:sco.start(2)] + body + patched[sco.end(2):]
    return '/* SMARTKEYBOARD_SCO_TEST_V1: experimental BlueZ ownership corrections. */\n' + patched


def prepare(source_dir, output_root):
    source_dir = source_dir.resolve(strict=True)
    original = (source_dir / 'aic_btusb.c').read_text()
    header = (source_dir / 'aic_btusb.h').read_text()
    patched = patch_source(original, header)  # Validate everything before writing.
    output_root.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix='bt-sco-test-', dir=str(output_root)))
    shutil.copytree(str(source_dir), str(output), dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('*.o', '*.ko', '*.mod', '*.mod.c', '.*.cmd',
                                                  '.tmp_versions', 'Module.symvers', 'modules.order', '.git'))
    (output / 'aic_btusb.c').write_text(patched)
    (output / 'smartkeyboard-sco-test.patch').write_text(''.join(difflib.unified_diff(
        original.splitlines(True), patched.splitlines(True), fromfile='original/aic_btusb.c', tofile='test/aic_btusb.c')))
    (output / 'smartkeyboard-sco-test.json').write_text(json.dumps({
        'experimental': True, 'originalSource': str(source_dir),
        'sourceSha256': hashlib.sha256(original.encode()).hexdigest(),
        'headerSha256': hashlib.sha256(header.encode()).hexdigest(),
        'installed': False}, indent=2))
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--output-root', type=Path, default=Path.home() / 'SmartKeyboard')
    args = parser.parse_args()
    if hasattr(os, 'geteuid') and os.geteuid() == 0:
        parser.error('Run as radxa, without sudo. This tool never installs a module.')
    if not args.prepare_only and sys.platform != 'linux':
        parser.error('Build on the Radxa; this PC can only use --prepare-only.')
    try:
        output = prepare(args.source, args.output_root)
        print('Experimental source:', output, flush=True)
        print('Original source and installed driver were left unchanged.', flush=True)
        if not args.prepare_only:
            kernel = os.uname().release
            subprocess.run(['make', '-C', str(output), '-j2', 'CONFIG_PLATFORM_UBUNTU=y'], check=True)
            module = output / 'aic_btusb.ko'
            name = subprocess.check_output(['/sbin/modinfo', '-F', 'name', str(module)], text=True).strip()
            version = subprocess.check_output(['/sbin/modinfo', '-F', 'vermagic', str(module)], text=True).split()[0]
            if name != 'aic_btusb' or version != kernel:
                raise ValueError('Built module metadata does not match the running kernel.')
            print('Build verified:', module, flush=True)
        print('NOT installed or loaded. Do not retry microphone mode on the old driver.', flush=True)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print('Stopped:', error, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
