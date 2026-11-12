#!/bin/bash
# Restart only this project's main Chromium process, preserving its profile.
set -eu
app_home="$HOME/SmartKeyboard"
profile="$app_home/kiosk-profile"
if [ ! -f "$app_home/scripts/launch-kiosk.sh" ]; then echo 'Launcher missing'; exit 1; fi
python3 - "$profile" <<'PY'
import os
import signal
import sys
import time
from pathlib import Path
profile_argument='--user-data-dir='+sys.argv[1]
targets=[]
for entry in Path('/proc').iterdir():
    if not entry.name.isdigit(): continue
    try:
        if entry.stat().st_uid != os.getuid(): continue
        args=[part.decode(errors='replace') for part in (entry/'cmdline').read_bytes().split(b'\0') if part]
        if not args or profile_argument not in args or any(arg.startswith('--type=') for arg in args): continue
        if Path(args[0]).name not in ('chromium','chromium-browser','chrome'): continue
        targets.append(int(entry.name))
    except (OSError,ValueError): continue
for pid in targets:
    try: os.kill(pid,signal.SIGTERM)
    except ProcessLookupError: pass
deadline=time.monotonic()+12
while time.monotonic()<deadline:
    alive=[]
    for pid in targets:
        try: os.kill(pid,0); alive.append(pid)
        except ProcessLookupError: pass
    if not alive: break
    time.sleep(0.2)
else:
    raise SystemExit('Smart Keyboard browser did not close; no force-kill performed. Paste this output.')
print('Closed only Smart Keyboard browser PIDs:',targets)
PY
nohup /bin/bash "$app_home/scripts/launch-kiosk.sh" >/dev/null 2>&1 </dev/null &
echo "Smart Keyboard relaunch requested. Log: $app_home/logs/kiosk-startup.log"
