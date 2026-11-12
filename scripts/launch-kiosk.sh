#!/bin/bash
set -eu

app_home="$HOME/SmartKeyboard"
mkdir -p "$app_home/logs"
exec >> "$app_home/logs/kiosk-startup.log" 2>&1
printf '\nSmart Keyboard launch: %s\n' "$(date -Is)"

if [ ! -f "$app_home/src/index.html" ]; then
  echo "Missing $app_home/src/index.html; copy src before launching."
  exit 1
fi

# Keep this project separate from all existing Chromium profiles and EZ Signage.
profile="$app_home/kiosk-profile"
# MobaXterm can export a forwarded DISPLAY such as localhost:10.0.
# This launcher always targets the already-verified physical touchscreen.
export DISPLAY=:0
export XAUTHORITY="$HOME/.Xauthority"
printf 'Target display: %s; authority: %s\n' "$DISPLAY" "$XAUTHORITY"
browser=$(command -v chromium || command -v chromium-browser || true)
if [ -z "$browser" ]; then echo 'Chromium is not installed.'; exit 1; fi

# Desktop autostart supplies the session; allow X a short time to become ready.
if command -v xset >/dev/null 2>&1; then
  ready=false
  for attempt in $(seq 1 30); do
    if xset q >/dev/null 2>&1; then ready=true; break; fi
    sleep 1
  done
  if [ "$ready" != true ]; then echo 'Display session did not become ready.'; exit 1; fi
  # Wake once at launch; do not change screen timers or desktop settings.
  xset s reset || true
  xset dpms force on || true
fi

exec "$browser" \
  --user-data-dir="$profile" \
  --no-first-run --disable-gpu --kiosk \
  "file://$app_home/src/index.html"
